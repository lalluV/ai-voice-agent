from __future__ import annotations

from collections.abc import AsyncIterator

from app.domain.models import CallSession, ToolCall, ToolResult
from app.providers.base import ProviderAudioEvent, VoiceProvider


class OpenAIRealtimeProvider(VoiceProvider):
    """
    Stub for future OpenAI Realtime support.

    TODO: Implement against the official OpenAI Realtime API / SDK after consulting
    current documentation. Do not invent message schemas here.
    Required surface once implemented:
      - connect / disconnect
      - send_audio (PCM format dictated by OpenAI docs)
      - audio_stream with interruption events
      - function calling via handle_tool_call / send_tool_result
    """

    async def connect(self, session: CallSession) -> None:
        raise NotImplementedError(
            "TODO: OpenAI Realtime provider not implemented — "
            "consult OpenAI Realtime API docs and wire official SDK."
        )

    async def disconnect(self) -> None:
        return None

    async def send_audio(self, pcm16_16k: bytes) -> None:
        raise NotImplementedError("TODO: OpenAI Realtime send_audio")

    async def audio_stream(self) -> AsyncIterator[ProviderAudioEvent]:
        raise NotImplementedError("TODO: OpenAI Realtime audio_stream")
        yield  # pragma: no cover

    async def handle_tool_call(self, call: ToolCall) -> ToolResult:
        return ToolResult(
            id=call.id,
            name=call.name,
            success=False,
            error="OpenAI Realtime provider not implemented",
        )
