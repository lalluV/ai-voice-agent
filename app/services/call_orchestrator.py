from __future__ import annotations

import asyncio
from typing import Any

from fastapi import WebSocket

from app.audio.bridge import AudioBridge
from app.core.config import Settings
from app.core.logging import get_logger
from app.core.metrics import ERRORS
from app.domain.enums import CallEndReason, SessionStatus
from app.domain.models import CallSession, Tenant
from app.providers.base import VoiceProvider
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
        self._prewarm: dict[str, VoiceProvider] = {}
        self._prewarm_tasks: dict[str, asyncio.Task[None]] = {}

    def get_live(self, session_id: str) -> LiveCallContext | None:
        return self._live.get(session_id)

    def schedule_prewarm_outbound(self, session: CallSession, tenant: Tenant) -> None:
        """Kick off Gemini connect during ring; do not await."""
        existing = self._prewarm_tasks.get(session.session_id)
        if existing and not existing.done():
            return
        task = asyncio.create_task(
            self._prewarm_outbound(session, tenant),
            name=f"prewarm-{session.session_id}",
        )
        self._prewarm_tasks[session.session_id] = task

    async def _prewarm_outbound(self, session: CallSession, tenant: Tenant) -> None:
        logger.info(
            "outbound_prewarm_started",
            session_id=session.session_id,
            tenant_id=tenant.tenant_id,
            call_id=session.call_id,
        )
        try:
            provider = self._providers.create(tenant)
            await provider.connect(session)
            # Only store if session still alive (not hung up during connect)
            if self._sessions.get(session.session_id) is None:
                await provider.disconnect()
                logger.info(
                    "outbound_prewarm_discarded",
                    session_id=session.session_id,
                    reason="session_ended",
                )
                return
            self._prewarm[session.session_id] = provider
            logger.info(
                "outbound_prewarm_ready",
                session_id=session.session_id,
                tenant_id=tenant.tenant_id,
            )
        except asyncio.CancelledError:
            logger.info("outbound_prewarm_cancelled", session_id=session.session_id)
            raise
        except Exception:
            ERRORS.labels(component="orchestrator").inc()
            logger.exception(
                "outbound_prewarm_failed",
                session_id=session.session_id,
                tenant_id=tenant.tenant_id,
            )
        finally:
            self._prewarm_tasks.pop(session.session_id, None)

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

        provider = await self._take_prewarmed_provider(session)
        if provider is None:
            logger.info(
                "outbound_prewarm_miss",
                session_id=session.session_id,
                direction=session.direction,
            )
            provider = self._providers.create(tenant)
            await provider.connect(session)
        else:
            logger.info(
                "outbound_prewarm_reused",
                session_id=session.session_id,
                tenant_id=tenant.tenant_id,
            )
            arm = getattr(provider, "arm_greeting_grace", None)
            if callable(arm):
                arm()

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

    async def _take_prewarmed_provider(
        self, session: CallSession
    ) -> VoiceProvider | None:
        task = self._prewarm_tasks.get(session.session_id)
        if task is not None and not task.done():
            try:
                await task
            except Exception:
                logger.exception(
                    "outbound_prewarm_await_failed",
                    session_id=session.session_id,
                )
        return self._prewarm.pop(session.session_id, None)

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
        task = self._prewarm_tasks.pop(session_id, None)
        if task is not None and not task.done():
            task.cancel()
            await asyncio.gather(task, return_exceptions=True)

        prewarm = self._prewarm.pop(session_id, None)
        ctx = self._live.pop(session_id, None)

        provider: VoiceProvider | None = None
        bridge: AudioBridge | None = None
        if ctx is not None:
            provider = ctx.provider
            bridge = ctx.bridge
        elif prewarm is not None:
            provider = prewarm

        if bridge is not None:
            await bridge.stop()
        if provider is not None:
            try:
                await provider.disconnect()
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
