from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.domain.models import CallSession, Tenant, ToolResult


class ToolHandler(ABC):
    name: str
    description: str
    parameters: dict[str, Any]

    @abstractmethod
    async def execute(
        self,
        *,
        tenant: Tenant,
        session: CallSession,
        arguments: dict[str, Any],
        call_id: str,
    ) -> ToolResult:
        raise NotImplementedError
