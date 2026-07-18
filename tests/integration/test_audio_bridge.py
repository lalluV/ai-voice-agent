from __future__ import annotations

import asyncio
import base64
from collections.abc import AsyncIterator

import pytest

from app.audio.bridge import AudioBridge
from app.audio.codec import pcm16_to_mulaw
from app.domain.models import CallSession, ToolCall, ToolResult
from app.providers.base import ProviderAudioEvent, ProviderEventType, VoiceProvider


class MockProvider(VoiceProvider):
    def __init__(self) -> None:
        self.sent: list[bytes] = []
        self._q: asyncio.Queue[ProviderAudioEvent | None] = asyncio.Queue()

    async def connect(self, session: CallSession) -> None:
        return None

    async def disconnect(self) -> None:
        await self._q.put(None)

    async def send_audio(self, pcm16_16k: bytes) -> None:
        self.sent.append(pcm16_16k)

    async def audio_stream(self) -> AsyncIterator[ProviderAudioEvent]:
        while True:
            item = await self._q.get()
            if item is None:
                break
            yield item

    async def handle_tool_call(self, call: ToolCall) -> ToolResult:
        return ToolResult(id=call.id, name=call.name, success=True)

    async def emit(self, event: ProviderAudioEvent) -> None:
        await self._q.put(event)


@pytest.mark.asyncio
async def test_bridge_forwards_and_clears_on_interrupt() -> None:
    sent_json: list[dict] = []

    async def send_json(payload: dict) -> None:
        sent_json.append(payload)

    provider = MockProvider()
    bridge = AudioBridge(
        provider=provider,
        send_json=send_json,
        stream_id="stream-1",
        tenant_id="demo",
        plivo_sample_rate=8000,
        provider_input_rate=16000,
        provider_output_rate=24000,
        use_mulaw=True,
    )
    await bridge.start()

    # Plivo -> provider
    pcm8k = bytes([0, 1] * 160)
    mulaw = pcm16_to_mulaw(pcm8k)
    await bridge.on_plivo_media(base64.b64encode(mulaw).decode())
    assert provider.sent
    assert len(provider.sent[0]) == len(pcm8k) * 2  # resampled to 16k

    # Provider audio -> Plivo
    pcm24k = bytes([0, 1] * 480)
    await provider.emit(
        ProviderAudioEvent(
            type=ProviderEventType.AUDIO, pcm16=pcm24k, sample_rate=24000
        )
    )
    await asyncio.sleep(0.05)
    assert any(m.get("event") == "playAudio" for m in sent_json)

    # Interrupt
    await provider.emit(ProviderAudioEvent(type=ProviderEventType.INTERRUPTED))
    await asyncio.sleep(0.05)
    assert any(m.get("event") == "clearAudio" for m in sent_json)

    await provider.disconnect()
    await bridge.stop()
