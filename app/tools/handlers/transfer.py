from __future__ import annotations

from typing import Any, Awaitable, Callable

from app.domain.models import CallSession, Tenant, ToolResult
from app.tools.base import ToolHandler

TransferFn = Callable[[CallSession, Tenant, str | None, str | None], Awaitable[dict]]


class TransferCallHandler(ToolHandler):
    name = "transferCall"
    description = "Transfer call via Plivo"
    parameters: dict[str, Any] = {}

    def __init__(self, transfer_fn: TransferFn) -> None:
        self._transfer_fn = transfer_fn

    async def execute(
        self,
        *,
        tenant: Tenant,
        session: CallSession,
        arguments: dict[str, Any],
        call_id: str,
    ) -> ToolResult:
        destination = arguments.get("destination") or tenant.transfer_number
        if not destination:
            return ToolResult(
                id=call_id,
                name=self.name,
                success=False,
                error="No transfer number configured for this hospital",
            )
        try:
            data = await self._transfer_fn(
                session, tenant, destination, arguments.get("reason")
            )
            return ToolResult(id=call_id, name=self.name, success=True, data=data)
        except Exception as exc:  # noqa: BLE001 — surface to model as tool error
            return ToolResult(
                id=call_id, name=self.name, success=False, error=str(exc)
            )
