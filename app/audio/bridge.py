from __future__ import annotations

import asyncio
import base64
from collections.abc import Awaitable, Callable
from typing import Any

from app.audio.codec import mulaw_to_pcm16, pcm16_to_mulaw
from app.audio.resample import resample_pcm16
from app.core.logging import get_logger
from app.core.metrics import INTERRUPTIONS
from app.providers.base import ProviderAudioEvent, ProviderEventType, VoiceProvider

logger = get_logger(__name__)

SendJson = Callable[[dict[str, Any]], Awaitable[None]]


class AudioBridge:
    """
    Bidirectional audio bridge between Plivo (μ-law 8 kHz) and VoiceProvider (PCM 16/24 kHz).
    """

    def __init__(
        self,
        *,
        provider: VoiceProvider,
        send_json: SendJson,
        stream_id: str,
        tenant_id: str,
        plivo_sample_rate: int = 8000,
        provider_input_rate: int = 16000,
        provider_output_rate: int = 24000,
        use_mulaw: bool = True,
    ) -> None:
        self._provider = provider
        self._send_json = send_json
        self._stream_id = stream_id
        self._tenant_id = tenant_id
        self._plivo_rate = plivo_sample_rate
        self._in_rate = provider_input_rate
        self._out_rate = provider_output_rate
        self._use_mulaw = use_mulaw
        self._tasks: list[asyncio.Task] = []
        self._closed = asyncio.Event()
        self._playback_chunks = 0

    async def start(self) -> None:
        self._tasks = [
            asyncio.create_task(self._provider_to_plivo(), name="provider_to_plivo"),
        ]

    async def on_plivo_media(self, payload_b64: str) -> None:
        if self._closed.is_set():
            return
        raw = base64.b64decode(payload_b64)
        if self._use_mulaw:
            pcm8k = mulaw_to_pcm16(raw)
        else:
            pcm8k = raw
        pcm16k = resample_pcm16(pcm8k, self._plivo_rate, self._in_rate)
        await self._provider.send_audio(pcm16k)

    async def clear_plivo_audio(self) -> None:
        await self._send_json({"event": "clearAudio", "streamId": self._stream_id})

    async def _provider_to_plivo(self) -> None:
        try:
            async for event in self._provider.audio_stream():
                if self._closed.is_set():
                    break
                if event.type == ProviderEventType.INTERRUPTED:
                    INTERRUPTIONS.labels(tenant_id=self._tenant_id).inc()
                    await self.clear_plivo_audio()
                    logger.info(
                        "barge_in_cleared_audio",
                        stream_id=self._stream_id,
                        tenant_id=self._tenant_id,
                    )
                    continue
                if event.type == ProviderEventType.AUDIO and event.pcm16:
                    await self._play_pcm(event.pcm16)
                if event.type == ProviderEventType.ERROR:
                    logger.error(
                        "provider_event_error",
                        error=event.error,
                        tenant_id=self._tenant_id,
                    )
        except asyncio.CancelledError:
            raise
        except Exception:
            logger.exception("provider_to_plivo_failed", tenant_id=self._tenant_id)
        finally:
            self._closed.set()

    async def _play_pcm(self, pcm_provider_rate: bytes) -> None:
        pcm_plivo = resample_pcm16(pcm_provider_rate, self._out_rate, self._plivo_rate)
        if self._use_mulaw:
            payload = pcm16_to_mulaw(pcm_plivo)
            content_type = "audio/x-mulaw"
        else:
            payload = pcm_plivo
            content_type = "audio/x-l16"
        await self._send_json(
            {
                "event": "playAudio",
                "media": {
                    "contentType": content_type,
                    "sampleRate": self._plivo_rate,
                    "payload": base64.b64encode(payload).decode("ascii"),
                },
            }
        )
        self._playback_chunks += 1

    async def stop(self) -> None:
        self._closed.set()
        for task in self._tasks:
            task.cancel()
        if self._tasks:
            await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks.clear()
