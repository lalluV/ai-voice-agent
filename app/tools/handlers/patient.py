from __future__ import annotations

from typing import Any

import httpx

from app.domain.models import CallSession, Tenant, ToolResult
from app.hms import endpoints
from app.hms.client import HmsClient
from app.tools.base import ToolHandler


class PatientSearchHandler(ToolHandler):
    name = "patientSearch"
    description = "Search patients by phone or name"
    parameters: dict[str, Any] = {}

    def __init__(self, hms: HmsClient) -> None:
        self._hms = hms

    async def execute(
        self,
        *,
        tenant: Tenant,
        session: CallSession,
        arguments: dict[str, Any],
        call_id: str,
    ) -> ToolResult:
        phone = arguments.get("phone")
        try:
            if phone:
                data = await self._hms.get(
                    tenant, endpoints.PATIENT_BY_PHONE.format(phone=phone)
                )
            else:
                params = {
                    k: v
                    for k, v in {
                        "search": arguments.get("search") or arguments.get("name"),
                        "limit": 10,
                    }.items()
                    if v
                }
                data = await self._hms.get(tenant, endpoints.PATIENTS, params=params)
            return ToolResult(id=call_id, name=self.name, success=True, data=data)
        except httpx.HTTPError as exc:
            return ToolResult(
                id=call_id, name=self.name, success=False, error=str(exc)
            )


class CreatePatientHandler(ToolHandler):
    name = "createPatient"
    description = "Register a new patient"
    parameters: dict[str, Any] = {}

    def __init__(self, hms: HmsClient) -> None:
        self._hms = hms

    async def execute(
        self,
        *,
        tenant: Tenant,
        session: CallSession,
        arguments: dict[str, Any],
        call_id: str,
    ) -> ToolResult:
        body = {
            "name": arguments["name"],
            "phone": arguments.get("phone") or arguments.get("mobile"),
            "mobile": arguments.get("phone") or arguments.get("mobile"),
            "gender": arguments["gender"],
            "age": arguments["age"],
        }
        try:
            data = await self._hms.post(tenant, endpoints.PATIENTS, json=body)
            return ToolResult(id=call_id, name=self.name, success=True, data=data)
        except httpx.HTTPError as exc:
            return ToolResult(
                id=call_id, name=self.name, success=False, error=str(exc)
            )
