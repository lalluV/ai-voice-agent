from __future__ import annotations

import json
from typing import Any

import httpx
from redis.asyncio import Redis

from app.core.config import Settings
from app.domain.models import CallSession, Tenant, ToolResult
from app.hms import endpoints
from app.hms.client import HmsClient
from app.tools.base import ToolHandler


class DepartmentListHandler(ToolHandler):
    name = "departmentList"
    description = "List departments"
    parameters: dict[str, Any] = {}

    def __init__(
        self, hms: HmsClient, redis: Redis | None, settings: Settings
    ) -> None:
        self._hms = hms
        self._redis = redis
        self._ttl = settings.department_cache_ttl_seconds

    async def execute(
        self,
        *,
        tenant: Tenant,
        session: CallSession,
        arguments: dict[str, Any],
        call_id: str,
    ) -> ToolResult:
        cache_key = f"voice:depts:{tenant.tenant_id}"
        if self._redis is not None:
            cached = await self._redis.get(cache_key)
            if cached:
                return ToolResult(
                    id=call_id, name=self.name, success=True, data=json.loads(cached)
                )
        try:
            data = await self._hms.get(tenant, endpoints.DEPARTMENTS)
            if self._redis is not None:
                await self._redis.set(cache_key, json.dumps(data), ex=self._ttl)
            return ToolResult(id=call_id, name=self.name, success=True, data=data)
        except httpx.HTTPError as exc:
            return ToolResult(
                id=call_id, name=self.name, success=False, error=str(exc)
            )


class DoctorAvailabilityHandler(ToolHandler):
    """
    TODO: HMS has no dedicated doctor availability / slot API.
    Fallback: list doctors via staff type + optional appointment scan.
    """

    name = "doctorAvailability"
    description = "Approximate doctor availability"
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
        try:
            doctors = await self._hms.get(
                tenant, endpoints.STAFF_BY_TYPE.format(staff_type="Doctor")
            )
            doctor_name = (arguments.get("doctorName") or "").lower()
            department = (arguments.get("department") or "").lower()
            if isinstance(doctors, list) and (doctor_name or department):
                filtered = []
                for d in doctors:
                    name = str(d.get("name", "")).lower()
                    dept = str(d.get("department", "")).lower()
                    if doctor_name and doctor_name not in name:
                        continue
                    if department and department not in dept:
                        continue
                    filtered.append(d)
                doctors = filtered
            # TODO: replace with real availability API when HMS exposes slots
            return ToolResult(
                id=call_id,
                name=self.name,
                success=True,
                data={
                    "doctors": doctors,
                    "availability": None,
                    "note": (
                        "TODO: No dedicated doctorAvailability API in HMS. "
                        "Returned staff directory filter only."
                    ),
                },
            )
        except httpx.HTTPError as exc:
            return ToolResult(
                id=call_id, name=self.name, success=False, error=str(exc)
            )


class LabReportsHandler(ToolHandler):
    """Partial: uses diagnostics receipts listing when available."""

    name = "labReports"
    description = "Lab report lookup"
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
        params = {
            k: v
            for k, v in {
                "search": arguments.get("phone")
                or arguments.get("umr")
                or arguments.get("patientId"),
                "limit": 10,
            }.items()
            if v
        }
        try:
            data = await self._hms.get(
                tenant, endpoints.DIAGNOSTICS_RECEIPTS, params=params
            )
            return ToolResult(
                id=call_id,
                name=self.name,
                success=True,
                data={
                    "results": data,
                    "note": (
                        "TODO: Confirm exact lab report endpoint with HMS team; "
                        "using diagnostics-receipts as best-effort."
                    ),
                },
            )
        except httpx.HTTPError as exc:
            return ToolResult(
                id=call_id,
                name=self.name,
                success=False,
                error=(
                    f"{exc}; TODO: HMS lab report API may differ — "
                    "consult diagnostics routes."
                ),
            )


class GenerateBillHandler(ToolHandler):
    name = "generateBill"
    description = "Interim bill pointer"
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
        patient_id = arguments.get("patientId") or arguments.get("umr")
        try:
            if not patient_id and arguments.get("phone"):
                patients = await self._hms.get(
                    tenant,
                    endpoints.PATIENT_BY_PHONE.format(phone=arguments["phone"]),
                )
                if isinstance(patients, list) and patients:
                    patient_id = (
                        patients[0].get("UMRNo")
                        or patients[0].get("umr")
                        or patients[0].get("_id")
                    )
            if not patient_id:
                return ToolResult(
                    id=call_id,
                    name=self.name,
                    success=False,
                    error="patientId or phone required",
                )
            data = await self._hms.get(
                tenant,
                endpoints.PATIENT_INTERIM_BILL.format(patient_id=patient_id),
            )
            return ToolResult(
                id=call_id,
                name=self.name,
                success=True,
                data={
                    "bill": data,
                    "note": "Closest HMS endpoint: patients/:id/interim-bill",
                },
            )
        except httpx.HTTPError as exc:
            return ToolResult(
                id=call_id, name=self.name, success=False, error=str(exc)
            )


class SendWhatsappHandler(ToolHandler):
    """
    TODO: HMS WhatsApp today is prescription-scoped only
    (POST /prescriptions/:patientId/:prescriptionId/send-whatsapp).
    """

    name = "sendWhatsapp"
    description = "Send WhatsApp (limited)"
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
        patient_id = arguments.get("patientId")
        prescription_id = arguments.get("prescriptionId")
        if not patient_id or not prescription_id:
            return ToolResult(
                id=call_id,
                name=self.name,
                success=False,
                error=(
                    "TODO: General WhatsApp messaging is not available in HMS. "
                    "Requires patientId and prescriptionId for prescription WhatsApp."
                ),
            )
        try:
            data = await self._hms.post(
                tenant,
                endpoints.PRESCRIPTION_WHATSAPP.format(
                    patient_id=patient_id, prescription_id=prescription_id
                ),
                json={},
            )
            return ToolResult(id=call_id, name=self.name, success=True, data=data)
        except httpx.HTTPError as exc:
            return ToolResult(
                id=call_id, name=self.name, success=False, error=str(exc)
            )
