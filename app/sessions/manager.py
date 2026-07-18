from __future__ import annotations

import asyncio
from typing import Any

from app.core.logging import get_logger
from app.core.metrics import ACTIVE_SESSIONS, CALLS_ENDED, CALLS_STARTED, CONCURRENT_CALLS
from app.domain.enums import CallDirection, CallEndReason, SessionStatus
from app.domain.models import CallSession, utcnow
from app.repositories.call_logs import CallLogRepository

logger = get_logger(__name__)


class SessionManager:
    def __init__(self, call_logs: CallLogRepository) -> None:
        self._call_logs = call_logs
        self._sessions: dict[str, CallSession] = {}
        self._lock = asyncio.Lock()

    @property
    def active_count(self) -> int:
        return len(self._sessions)

    def get(self, session_id: str) -> CallSession | None:
        return self._sessions.get(session_id)

    def get_by_call_id(self, call_id: str) -> CallSession | None:
        for session in self._sessions.values():
            if session.call_id == call_id:
                return session
        return None

    async def create(
        self,
        *,
        tenant_id: str,
        direction: CallDirection,
        from_number: str | None = None,
        to_number: str | None = None,
        call_id: str | None = None,
        metadata: dict[str, Any] | None = None,
    ) -> CallSession:
        session = CallSession(
            tenant_id=tenant_id,
            direction=direction,
            from_number=from_number,
            to_number=to_number,
            call_id=call_id,
            metadata=metadata or {},
            status=SessionStatus.CREATED,
        )
        async with self._lock:
            self._sessions[session.session_id] = session
        CONCURRENT_CALLS.inc()
        ACTIVE_SESSIONS.inc()
        CALLS_STARTED.labels(tenant_id=tenant_id).inc()
        await self._call_logs.upsert_from_session(session)
        logger.info(
            "call_started",
            session_id=session.session_id,
            tenant_id=tenant_id,
            direction=direction,
            from_number=from_number,
            to_number=to_number,
        )
        return session

    async def update(self, session: CallSession) -> None:
        self._sessions[session.session_id] = session
        await self._call_logs.upsert_from_session(session)

    async def end(
        self,
        session_id: str,
        *,
        reason: CallEndReason,
        error_message: str | None = None,
    ) -> CallSession | None:
        async with self._lock:
            session = self._sessions.pop(session_id, None)
        if session is None:
            return None
        session.status = SessionStatus.ENDED
        session.end_reason = reason
        session.ended_at = utcnow()
        session.error_message = error_message
        CONCURRENT_CALLS.dec()
        ACTIVE_SESSIONS.dec()
        CALLS_ENDED.labels(tenant_id=session.tenant_id, reason=reason.value).inc()
        await self._call_logs.upsert_from_session(session)
        duration = (
            (session.ended_at - session.started_at).total_seconds()
            if session.ended_at
            else None
        )
        logger.info(
            "call_ended",
            session_id=session.session_id,
            tenant_id=session.tenant_id,
            reason=reason,
            duration_seconds=duration,
            interruptions=session.interruption_count,
            tool_calls=session.tool_call_count,
            language=session.language,
        )
        return session

    async def drain(self, reason: CallEndReason = CallEndReason.SHUTDOWN) -> int:
        ids = list(self._sessions.keys())
        for sid in ids:
            await self.end(sid, reason=reason)
        return len(ids)
