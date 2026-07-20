from __future__ import annotations

import json

from app.core.logging import get_logger
from app.core.metrics import TOOL_CALLS
from app.domain.models import CallSession, Tenant, ToolCall, ToolResult
from app.tools.base import ToolHandler

logger = get_logger(__name__)

# Same tool+args more than this → block (stops tight API loops).
_MAX_IDENTICAL_CALLS = 2
# Same tool name this many times in a row → block even if args differ.
_MAX_CONSECUTIVE_SAME_TOOL = 3

_SPEAK_NOW = (
    "Speak this tool result to the caller now in their language. "
    "Use ONLY data present in this result — do not invent names, "
    "UMR, departments, amounts, statuses, or appointments. "
    "If empty/error, say unavailable/not found. "
    "Do not call the same tool again unless the caller gave new information."
)


class ToolRouter:
    def __init__(self, handlers: list[ToolHandler]) -> None:
        self._handlers = {h.name: h for h in handlers}

    def names(self) -> list[str]:
        return list(self._handlers)

    def _signature(self, call: ToolCall) -> str:
        try:
            args = json.dumps(call.arguments or {}, sort_keys=True, default=str)
        except TypeError:
            args = str(call.arguments)
        return f"{call.name}|{args}"

    def _block_if_looping(
        self, session: CallSession, call: ToolCall
    ) -> ToolResult | None:
        ctx = session.tool_context
        repeats: dict[str, int] = ctx.setdefault("tool_repeats", {})
        sig = self._signature(call)
        count = int(repeats.get(sig, 0)) + 1
        repeats[sig] = count

        recent: list[str] = ctx.setdefault("recent_tools", [])
        recent.append(call.name)
        if len(recent) > 12:
            del recent[:-12]

        consecutive = 0
        for name in reversed(recent):
            if name != call.name:
                break
            consecutive += 1

        if count > _MAX_IDENTICAL_CALLS or consecutive > _MAX_CONSECUTIVE_SAME_TOOL:
            logger.warning(
                "tool_call_blocked_loop",
                tool=call.name,
                session_id=session.session_id,
                identical_count=count,
                consecutive=consecutive,
            )
            return ToolResult(
                id=call.id,
                name=call.name,
                success=False,
                error=(
                    "Stop calling this tool in a loop. Speak to the caller now with "
                    "what you already know. Do not invent data. Offer human transfer "
                    "if you cannot help."
                ),
                data={
                    "blocked": True,
                    "do_not_retry": True,
                    "instruction": _SPEAK_NOW,
                },
            )
        return None

    @staticmethod
    def _with_speak_instruction(result: ToolResult) -> ToolResult:
        data = result.data if isinstance(result.data, dict) else {"result": result.data}
        if data is None:
            data = {}
        data = dict(data)
        data.setdefault("instruction", _SPEAK_NOW)
        return ToolResult(
            id=result.id,
            name=result.name,
            success=result.success,
            data=data,
            error=result.error,
        )

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

        blocked = self._block_if_looping(session, call)
        if blocked is not None:
            TOOL_CALLS.labels(
                tenant_id=tenant.tenant_id, tool=call.name, status="blocked"
            ).inc()
            return blocked

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
            return self._with_speak_instruction(result)
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
                id=call.id,
                name=call.name,
                success=False,
                error=str(exc),
                data={"instruction": _SPEAK_NOW, "do_not_retry": True},
            )
