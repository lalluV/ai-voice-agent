from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request

from app.core.security import require_admin_api_key
from app.domain.models import CallLog
from app.repositories.call_logs import CallLogRepository

router = APIRouter(
    prefix="/admin/call-logs",
    tags=["admin"],
    dependencies=[Depends(require_admin_api_key)],
)


@router.get("", response_model=list[CallLog])
async def list_call_logs(
    request: Request,
    tenant_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
) -> list[CallLog]:
    call_logs: CallLogRepository = request.app.state.call_logs
    return await call_logs.list_recent(tenant_id=tenant_id, limit=limit)
