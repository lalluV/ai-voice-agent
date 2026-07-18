#!/usr/bin/env python3
"""
Example load test: N concurrent fake Plivo streams against a mocked provider bridge.

Usage:
  python scripts/load_test_example.py --concurrency 50 --chunks 100

This does not call Gemini or Plivo. It stress-tests codec/resample + bridge fan-in.
"""

from __future__ import annotations

import argparse
import asyncio
import base64
import time
from collections.abc import AsyncIterator

from app.audio.bridge import AudioBridge
from app.audio.codec import pcm16_to_mulaw
from app.domain.models import CallSession, ToolCall, ToolResult
from app.providers.base import ProviderAudioEvent, ProviderEventType, VoiceProvider


class SilentProvider(VoiceProvider):
    def __init__(self) -> None:
        self._q: asyncio.Queue[ProviderAudioEvent | None] = asyncio.Queue()

    async def connect(self, session: CallSession) -> None:
        return None

    async def disconnect(self) -> None:
        await self._q.put(None)

    async def send_audio(self, pcm16_16k: bytes) -> None:
        # Echo tiny silence burst occasionally
        if len(pcm16_16k) > 0 and len(pcm16_16k) % 640 == 0:
            await self._q.put(
                ProviderAudioEvent(
                    type=ProviderEventType.AUDIO,
                    pcm16=b"\x00\x00" * 240,
                    sample_rate=24000,
                )
            )

    async def audio_stream(self) -> AsyncIterator[ProviderAudioEvent]:
        while True:
            item = await self._q.get()
            if item is None:
                break
            yield item

    async def handle_tool_call(self, call: ToolCall) -> ToolResult:
        return ToolResult(id=call.id, name=call.name, success=True)


async def run_one(stream_idx: int, chunks: int) -> int:
    sent = 0

    async def send_json(_payload: dict) -> None:
        nonlocal sent
        sent += 1

    provider = SilentProvider()
    bridge = AudioBridge(
        provider=provider,
        send_json=send_json,
        stream_id=f"load-{stream_idx}",
        tenant_id="loadtest",
    )
    await bridge.start()
    pcm8k = bytes([0, 1] * 160)
    payload = base64.b64encode(pcm16_to_mulaw(pcm8k)).decode()
    for _ in range(chunks):
        await bridge.on_plivo_media(payload)
        await asyncio.sleep(0)  # yield
    await provider.disconnect()
    await bridge.stop()
    return sent


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--concurrency", type=int, default=20)
    parser.add_argument("--chunks", type=int, default=50)
    args = parser.parse_args()

    started = time.perf_counter()
    results = await asyncio.gather(
        *[run_one(i, args.chunks) for i in range(args.concurrency)]
    )
    elapsed = time.perf_counter() - started
    total_chunks = args.concurrency * args.chunks
    print(
        f"concurrency={args.concurrency} chunks={args.chunks} "
        f"elapsed_s={elapsed:.3f} inbound_chunks={total_chunks} "
        f"outbound_events={sum(results)} "
        f"chunks_per_s={total_chunks / elapsed:.1f}"
    )


if __name__ == "__main__":
    asyncio.run(main())
