from __future__ import annotations

import re
from typing import Any, Awaitable, Callable

from app.domain.models import CallSession, Tenant, ToolResult, _normalize_phone
from app.tools.base import ToolHandler

TransferFn = Callable[[CallSession, Tenant, str | None, str | None], Awaitable[dict]]

# Plivo Dial <Number> expects E.164-ish digits, not labels like "receptionist".
_PHONE_RE = re.compile(r"^\+?\d{8,15}$")


def _resolve_destination(raw: Any, tenant: Tenant) -> str | None:
    if isinstance(raw, str):
        candidate = _normalize_phone(raw.strip())
        if _PHONE_RE.match(candidate):
            return candidate
    if tenant.transfer_number:
        configured = _normalize_phone(tenant.transfer_number.strip())
        if _PHONE_RE.match(configured):
            return configured
    return None


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
        destination = _resolve_destination(arguments.get("destination"), tenant)
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
