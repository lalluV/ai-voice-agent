from __future__ import annotations

from typing import Any

from fastapi import WebSocket

from app.audio.bridge import AudioBridge
from app.core.config import Settings
from app.core.logging import get_logger
from app.core.metrics import ERRORS
from app.domain.enums import CallEndReason, SessionStatus
from app.domain.models import CallSession, Tenant
from app.providers.registry import ProviderRegistry
from app.services.outbound import PlivoOutboundService
from app.sessions.manager import SessionManager
from app.sessions.state import LiveCallContext

logger = get_logger(__name__)


class CallOrchestrator:
    def __init__(
        self,
        *,
        settings: Settings,
        sessions: SessionManager,
        providers: ProviderRegistry,
        plivo: PlivoOutboundService,
    ) -> None:
        self._settings = settings
        self._sessions = sessions
        self._providers = providers
        self._plivo = plivo
        self._live: dict[str, LiveCallContext] = {}

    def get_live(self, session_id: str) -> LiveCallContext | None:
        return self._live.get(session_id)

    async def transfer(
        self,
        session: CallSession,
        tenant: Tenant,
        destination: str | None,
        reason: str | None,
    ) -> dict[str, Any]:
        if not session.call_id:
            raise RuntimeError("Cannot transfer: missing Plivo call id")
        dest = destination or tenant.transfer_number
        if not dest:
            raise RuntimeError("No transfer destination")
        session.status = SessionStatus.TRANSFERRING
        session.current_intent = "transfer"
        session.metadata["transfer_reason"] = reason
        await self._sessions.update(session)
        result = await self._plivo.transfer_call(
            call_uuid=session.call_id,
            destination=dest,
            caller_id=session.to_number,
        )
        await self._sessions.end(session.session_id, reason=CallEndReason.TRANSFER)
        self._live.pop(session.session_id, None)
        return result

    async def start_stream(
        self,
        *,
        websocket: WebSocket,
        session: CallSession,
        tenant: Tenant,
        stream_id: str,
        call_id: str | None,
    ) -> LiveCallContext:
        session.stream_id = stream_id
        if call_id:
            session.call_id = call_id
        session.status = SessionStatus.CONNECTING
        await self._sessions.update(session)

        provider = self._providers.create(tenant)
        await provider.connect(session)

        async def send_json(payload: dict[str, Any]) -> None:
            await websocket.send_json(payload)

        bridge = AudioBridge(
            provider=provider,
            send_json=send_json,
            stream_id=stream_id,
            tenant_id=tenant.tenant_id,
            plivo_sample_rate=self._settings.plivo_sample_rate,
            provider_input_rate=self._settings.gemini_input_sample_rate,
            provider_output_rate=self._settings.gemini_output_sample_rate,
            use_mulaw="mulaw" in self._settings.plivo_audio_content_type,
        )
        await bridge.start()

        session.status = SessionStatus.ACTIVE
        await self._sessions.update(session)

        ctx = LiveCallContext(
            session=session, tenant=tenant, provider=provider, bridge=bridge
        )
        self._live[session.session_id] = ctx
        logger.info(
            "stream_started",
            session_id=session.session_id,
            stream_id=stream_id,
            call_id=call_id,
            tenant_id=tenant.tenant_id,
        )
        return ctx

    async def on_media(self, session_id: str, payload_b64: str) -> None:
        ctx = self._live.get(session_id)
        if ctx and ctx.bridge:
            await ctx.bridge.on_plivo_media(payload_b64)

    async def end_stream(
        self,
        session_id: str,
        *,
        reason: CallEndReason = CallEndReason.HANGUP,
        error: str | None = None,
    ) -> None:
        ctx = self._live.pop(session_id, None)
        if ctx is None:
            await self._sessions.end(session_id, reason=reason, error_message=error)
            return
        if ctx.bridge:
            await ctx.bridge.stop()
        if ctx.provider:
            try:
                await ctx.provider.disconnect()
            except Exception:  # pragma: no cover
                ERRORS.labels(component="provider").inc()
                logger.exception("provider_disconnect_failed", session_id=session_id)
        await self._sessions.end(session_id, reason=reason, error_message=error)

    async def fail_politely_and_end(self, session_id: str, error: str) -> None:
        ERRORS.labels(component="orchestrator").inc()
        logger.error("call_failed", session_id=session_id, error=error)
        await self.end_stream(
            session_id, reason=CallEndReason.ERROR, error=error[:500]
        )
