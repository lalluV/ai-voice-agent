from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import AsyncIterator
from dataclasses import dataclass, field
from enum import StrEnum
from typing import Any

from app.domain.models import CallSession, ToolCall, ToolResult


class ProviderEventType(StrEnum):
    AUDIO = "audio"
    INTERRUPTED = "interrupted"
    TOOL_CALL = "tool_call"
    TEXT = "text"
    ERROR = "error"
    TURN_COMPLETE = "turn_complete"


@dataclass
class ProviderAudioEvent:
    type: ProviderEventType
    pcm16: bytes | None = None
    sample_rate: int | None = None
    tool_call: ToolCall | None = None
    text: str | None = None
    error: str | None = None
    raw: Any = field(default=None, repr=False)


class VoiceProvider(ABC):
    """AI voice provider interface — Gemini today, OpenAI Realtime later."""

    @abstractmethod
    async def connect(self, session: CallSession) -> None:
        raise NotImplementedError

    @abstractmethod
    async def disconnect(self) -> None:
        raise NotImplementedError

    @abstractmethod
    async def send_audio(self, pcm16_16k: bytes) -> None:
        raise NotImplementedError

    @abstractmethod
    def audio_stream(self) -> AsyncIterator[ProviderAudioEvent]:
        raise NotImplementedError

    @abstractmethod
    async def handle_tool_call(self, call: ToolCall) -> ToolResult:
        raise NotImplementedError

    async def send_tool_result(self, result: ToolResult) -> None:
        """Optional: providers that need explicit tool response override this."""
        return None

    def arm_greeting_grace(self) -> None:
        """Optional: re-arm call-start interrupt shield when playback begins."""
        return None
