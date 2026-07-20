from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from fastapi import WebSocket

from app.audio.bridge import AudioBridge
from app.domain.models import CallSession, Tenant
from app.providers.base import VoiceProvider


@dataclass
class LiveCallContext:
    session: CallSession
    tenant: Tenant
    provider: VoiceProvider | None = None
    bridge: AudioBridge | None = None
    websocket: WebSocket | None = None
    extras: dict[str, Any] = field(default_factory=dict)
