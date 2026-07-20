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
from app.tools.helpers import (
    hms_error_message,
    normalize_doctor_list,
    phone_missing_error,
    phone_missing_payload,
    slim_patients,
    slim_receipts,
    view_base_url_for_tenant,
)


class DepartmentListHandler(ToolHandler):
    name = "departmentList"
    description = "List hospital departments (HMS /departments)."
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
            # Slim for voice
            items = data if isinstance(data, list) else data.get("departments", [])
            slim = [
                {
                    "name": d.get("name"),
                    "code": d.get("department_code"),
                    "type": d.get("type"),
                }
                for d in items
                if isinstance(d, dict) and d.get("name")
            ][:30]
            payload = {"count": len(slim), "departments": slim}
            if self._redis is not None:
                await self._redis.set(cache_key, json.dumps(payload), ex=self._ttl)
            if not slim:
                return ToolResult(
                    id=call_id,
                    name=self.name,
                    success=False,
                    error=(
                        "No departments returned. Do NOT invent department names. "
                        "Tell the caller the list is unavailable and offer transfer."
                    ),
                    data={**payload, "do_not_retry": True},
                )
            payload["note"] = (
                "Speak ONLY these department names. Never invent departments."
            )
            return ToolResult(id=call_id, name=self.name, success=True, data=payload)
        except httpx.HTTPError as exc:
            return ToolResult(
                id=call_id,
                name=self.name,
                success=False,
                error=(
                    f"{hms_error_message(exc)}. Do NOT invent department names. "
                    "Tell the caller and offer transfer."
                ),
                data={"do_not_retry": True, "count": 0, "departments": []},
            )


class DoctorAvailabilityHandler(ToolHandler):
    name = "doctorAvailability"
    description = (
        "List/filter doctors from HMS GET /staff/type/Doctor. "
        "REQUIRED before naming any doctor or calling bookAppointment. "
        "Never invent doctor names."
    )
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
            raw = await self._hms.get(
                tenant, endpoints.STAFF_BY_TYPE.format(staff_type="Doctor")
            )
            doctors = normalize_doctor_list(raw)
            session.tool_context["doctors_all"] = doctors
            session.tool_context["doctors_fetched"] = True
            doctor_name = (arguments.get("doctorName") or "").lower().strip()
            department = (arguments.get("department") or "").lower().strip()
            filtered = doctors
            if doctor_name or department:
                filtered = []
                for d in doctors:
                    name = d["name"].lower()
                    dept = d.get("department", "").lower()
                    if doctor_name and doctor_name not in name:
                        continue
                    if department and department not in dept:
                        continue
                    filtered.append(d)
            session.tool_context["doctors"] = filtered
            slim = [
                {
                    "name": d["name"],
                    "department": d.get("department") or "",
                    "id": d.get("id"),
                }
                for d in filtered[:20]
            ]
            if not doctors:
                return ToolResult(
                    id=call_id,
                    name=self.name,
                    success=False,
                    error=(
                        "HMS returned no doctors. Do NOT invent doctor names. "
                        "Tell the caller the doctor list is unavailable and offer "
                        "human transfer. Do NOT call doctorAvailability again."
                    ),
                    data={
                        "count": 0,
                        "doctors": [],
                        "do_not_retry": True,
                    },
                )
            if not slim:
                return ToolResult(
                    id=call_id,
                    name=self.name,
                    success=False,
                    error=(
                        "No matching doctors for that name/department. "
                        "Do NOT invent names. Ask the caller for another doctor "
                        "name or department, then wait for their answer before "
                        "calling any tool again."
                    ),
                    data={
                        "count": 0,
                        "doctors": [],
                        "availableSample": [
                            {"name": d["name"], "department": d.get("department") or ""}
                            for d in doctors[:8]
                        ],
                        "do_not_retry": True,
                    },
                )
            return ToolResult(
                id=call_id,
                name=self.name,
                success=True,
                data={
                    "count": len(filtered),
                    "doctors": slim,
                    "note": (
                        "Read 2–3 names max, ask which one. "
                        "Use the exact doctorName from this list for bookAppointment. "
                        "Never invent doctors."
                    ),
                },
            )
        except httpx.HTTPError as exc:
            return ToolResult(
                id=call_id,
                name=self.name,
                success=False,
                error=(
                    f"{hms_error_message(exc)}. Do NOT invent doctor names. "
                    "Tell the caller and offer transfer. Do NOT retry this tool now."
                ),
                data={"do_not_retry": True, "count": 0, "doctors": []},
            )


class LabReportsHandler(ToolHandler):
    """HMS diagnostics-receipts (lab module)."""

    name = "labReports"
    description = (
        "Look up lab/diagnostics receipts. Prefer phone or UMR. "
        "Ask if neither is provided."
    )
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
        phone = (arguments.get("phone") or "").strip()
        umr = (arguments.get("umr") or arguments.get("patientId") or "").strip()
        if not phone and not umr:
            payload = phone_missing_payload(session)
            return ToolResult(
                id=call_id,
                name=self.name,
                success=False,
                error=phone_missing_error(session),
                data=payload,
            )
        try:
            if umr:
                raw = await self._hms.get(
                    tenant, endpoints.DIAGNOSTICS_BY_PATIENT.format(umr=umr)
                )
            else:
                # Prefer account-phone route; fallback to list search
                try:
                    raw = await self._hms.get(
                        tenant,
                        endpoints.DIAGNOSTICS_BY_ACCOUNT_PHONE.format(phone=phone),
                    )
                except httpx.HTTPError:
                    raw = await self._hms.get(
                        tenant,
                        endpoints.DIAGNOSTICS_RECEIPTS,
                        params={"search": phone, "limit": 10},
                    )
            receipts = slim_receipts(raw)
            if not receipts:
                return ToolResult(
                    id=call_id,
                    name=self.name,
                    success=False,
                    error=(
                        "No lab/diagnostics receipts found. Do NOT invent report "
                        "status. Tell the caller not found and offer transfer."
                    ),
                    data={"count": 0, "receipts": [], "do_not_retry": True},
                )
            return ToolResult(
                id=call_id,
                name=self.name,
                success=True,
                data={
                    "count": len(receipts),
                    "receipts": receipts,
                    "note": (
                        "Summarize ONLY these receipts. Never invent report status "
                        "or amounts."
                    ),
                },
            )
        except httpx.HTTPError as exc:
            return ToolResult(
                id=call_id,
                name=self.name,
                success=False,
                error=(
                    f"{hms_error_message(exc)}. Do NOT invent lab report data. "
                    "Tell the caller and offer transfer."
                ),
                data={"do_not_retry": True, "count": 0, "receipts": []},
            )


class GenerateBillHandler(ToolHandler):
    """HMS GET /patients/:UMRNo/interim-bill"""

    name = "generateBill"
    description = (
        "Fetch interim bill by UMR. If only phone is known, resolve patient first. "
        "Ask for phone/UMR if missing."
    )
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
        umr = (arguments.get("umr") or arguments.get("patientId") or "").strip()
        phone = (arguments.get("phone") or "").strip()
        try:
            if not umr and phone:
                patients_raw = await self._hms.get(
                    tenant, endpoints.PATIENT_BY_PHONE.format(phone=phone)
                )
                patients = slim_patients(patients_raw)
                if not patients:
                    return ToolResult(
                        id=call_id,
                        name=self.name,
                        success=False,
                        error="No patient found for that phone. Confirm the number.",
                    )
                if len(patients) > 1:
                    return ToolResult(
                        id=call_id,
                        name=self.name,
                        success=False,
                        error="Multiple patients on this phone. Ask which name/UMR.",
                        data={"patients": patients},
                    )
                umr = patients[0].get("umr") or ""
            if not umr:
                payload = phone_missing_payload(session)
                payload["missing"] = ["umr", "phone"]
                return ToolResult(
                    id=call_id,
                    name=self.name,
                    success=False,
                    error=phone_missing_error(session),
                    data=payload,
                )
            bill_params = (
                {"endDate": arguments["endDate"]}
                if arguments.get("endDate")
                else {}
            )
            data = await self._hms.get(
                tenant,
                endpoints.PATIENT_INTERIM_BILL.format(umr=umr),
                params=bill_params or None,
            )
            # Keep voice summary small
            summary = {
                "umr": umr,
                "balanceDue": data.get("balanceDue") if isinstance(data, dict) else None,
                "totalAdvancePaid": data.get("totalAdvancePaid")
                if isinstance(data, dict)
                else None,
                "patientName": (
                    (data.get("patient") or {}).get("name")
                    if isinstance(data, dict)
                    else None
                ),
            }
            return ToolResult(
                id=call_id,
                name=self.name,
                success=True,
                data={
                    "summary": summary,
                    "bill": data,
                    "note": (
                        "Speak ONLY balanceDue/summary from this result. "
                        "Never invent bill amounts."
                    ),
                },
            )
        except httpx.HTTPError as exc:
            return ToolResult(
                id=call_id,
                name=self.name,
                success=False,
                error=(
                    f"{hms_error_message(exc)}. Do NOT invent bill amounts. "
                    "Tell the caller and offer transfer."
                ),
                data={"do_not_retry": True},
            )


class SendWhatsappHandler(ToolHandler):
    """
    HMS prescription WhatsApp only:
    POST /prescriptions/:UMRNo/:prescriptionId/send-whatsapp
    Body requires viewBaseUrl.
    """

    name = "sendWhatsapp"
    description = (
        "Send prescription WhatsApp. Requires UMR (patientId) and prescriptionId. "
        "Ask if missing. Not for free-form messages."
    )
    parameters: dict[str, Any] = {}

    def __init__(self, hms: HmsClient, settings: Settings) -> None:
        self._hms = hms
        self._settings = settings

    async def execute(
        self,
        *,
        tenant: Tenant,
        session: CallSession,
        arguments: dict[str, Any],
        call_id: str,
    ) -> ToolResult:
        umr = (
            arguments.get("umr")
            or arguments.get("patientId")
            or ""
        ).strip()
        prescription_id = (arguments.get("prescriptionId") or "").strip()
        missing: list[str] = []
        if not umr:
            missing.append("umr")
        if not prescription_id:
            missing.append("prescriptionId")
        if missing:
            return ToolResult(
                id=call_id,
                name=self.name,
                success=False,
                error=(
                    "HMS WhatsApp is prescription-only. Need UMR and prescriptionId. "
                    f"Missing: {', '.join(missing)}. Ask the caller / look up patient first."
                ),
                data={"missing": missing},
            )
        view_base = view_base_url_for_tenant(
            tenant, self._settings.hms_origin_host_pattern
        )
        try:
            data = await self._hms.post(
                tenant,
                endpoints.PRESCRIPTION_WHATSAPP.format(
                    umr=umr, prescription_id=prescription_id
                ),
                json={"viewBaseUrl": view_base},
            )
            return ToolResult(id=call_id, name=self.name, success=True, data=data)
        except httpx.HTTPError as exc:
            return ToolResult(
                id=call_id,
                name=self.name,
                success=False,
                error=hms_error_message(exc),
            )
