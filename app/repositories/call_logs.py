from __future__ import annotations

from motor.motor_asyncio import AsyncIOMotorDatabase

from app.domain.models import CallLog, CallSession


class CallLogRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._col = db.call_logs

    async def upsert_from_session(self, session: CallSession) -> CallLog:
        duration = None
        if session.ended_at and session.started_at:
            duration = (session.ended_at - session.started_at).total_seconds()
        log = CallLog(
            session_id=session.session_id,
            tenant_id=session.tenant_id,
            call_id=session.call_id,
            direction=session.direction,
            from_number=session.from_number,
            to_number=session.to_number,
            language=session.language,
            status=session.status,
            end_reason=session.end_reason,
            interruption_count=session.interruption_count,
            tool_call_count=session.tool_call_count,
            duration_seconds=duration,
            error_message=session.error_message,
            metadata=session.metadata,
            started_at=session.started_at,
            ended_at=session.ended_at,
        )
        await self._col.update_one(
            {"session_id": session.session_id},
            {"$set": log.model_dump(mode="json")},
            upsert=True,
        )
        return log

    async def get(self, session_id: str) -> CallLog | None:
        doc = await self._col.find_one({"session_id": session_id}, {"_id": 0})
        return CallLog.model_validate(doc) if doc else None

    async def list_recent(
        self,
        *,
        tenant_id: str | None = None,
        limit: int = 50,
    ) -> list[CallLog]:
        query: dict = {}
        if tenant_id:
            query["tenant_id"] = tenant_id
        cursor = (
            self._col.find(query, {"_id": 0})
            .sort("started_at", -1)
            .limit(min(max(limit, 1), 200))
        )
        return [CallLog.model_validate(doc) async for doc in cursor]
