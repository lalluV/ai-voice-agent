from __future__ import annotations

from app.core.logging import get_logger
from app.core.metrics import TOOL_CALLS
from app.domain.models import CallSession, Tenant, ToolCall, ToolResult
from app.tools.base import ToolHandler

logger = get_logger(__name__)


class ToolRouter:
    def __init__(self, handlers: list[ToolHandler]) -> None:
        self._handlers = {h.name: h for h in handlers}

    def names(self) -> list[str]:
        return list(self._handlers)

    async def execute(
        self, *, tenant: Tenant, session: CallSession, call: ToolCall
    ) -> ToolResult:
        handler = self._handlers.get(call.name)
        if handler is None:
            TOOL_CALLS.labels(
                tenant_id=tenant.tenant_id, tool=call.name, status="unknown"
            ).inc()
            return ToolResult(
                id=call.id,
                name=call.name,
                success=False,
                error=f"Unknown tool: {call.name}",
            )
        logger.info(
            "tool_call_start",
            tool=call.name,
            tenant_id=tenant.tenant_id,
            session_id=session.session_id,
        )
        try:
            result = await handler.execute(
                tenant=tenant,
                session=session,
                arguments=call.arguments or {},
                call_id=call.id,
            )
            status = "ok" if result.success else "error"
            TOOL_CALLS.labels(
                tenant_id=tenant.tenant_id, tool=call.name, status=status
            ).inc()
            session.tool_call_count += 1
            return result
        except Exception as exc:  # noqa: BLE001
            TOOL_CALLS.labels(
                tenant_id=tenant.tenant_id, tool=call.name, status="exception"
            ).inc()
            logger.exception(
                "tool_call_failed",
                tool=call.name,
                tenant_id=tenant.tenant_id,
                session_id=session.session_id,
            )
            return ToolResult(
                id=call.id, name=call.name, success=False, error=str(exc)
            )
