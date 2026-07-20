from __future__ import annotations

from typing import Any

import httpx

from app.domain.models import CallSession, Tenant, ToolResult
from app.hms import endpoints
from app.hms.client import HmsClient
from app.tools.base import ToolHandler
from app.tools.helpers import (
    hms_error_message,
    phone_missing_error,
    phone_missing_payload,
    require_fields,
    slim_patients,
)


class PatientSearchHandler(ToolHandler):
    name = "patientSearch"
    description = (
        "Search patients by phone (preferred) or name/UMR. "
        "Ask for phone or name if neither is provided."
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
        search = (arguments.get("search") or arguments.get("name") or "").strip()
        if not phone and not search:
            payload = phone_missing_payload(session)
            return ToolResult(
                id=call_id,
                name=self.name,
                success=False,
                error=phone_missing_error(session),
                data=payload,
            )
        if search and len(search) < 2 and not phone:
            return ToolResult(
                id=call_id,
                name=self.name,
                success=False,
                error="Search text must be at least 2 characters. Ask again.",
                data={"missing": ["search"]},
            )
        try:
            if phone:
                raw = await self._hms.get(
                    tenant, endpoints.PATIENT_BY_PHONE.format(phone=phone)
                )
            else:
                raw = await self._hms.get(
                    tenant,
                    endpoints.PATIENTS,
                    params={"search": search, "limit": 10},
                )
            patients = slim_patients(raw)
            session.tool_context["last_patients"] = patients
            if not patients:
                return ToolResult(
                    id=call_id,
                    name=self.name,
                    success=False,
                    error=(
                        "No patient found. Do NOT invent a patient name or UMR. "
                        "Tell the caller not found and ask to confirm phone/name, "
                        "or offer transfer / createPatient if they want to register."
                    ),
                    data={"count": 0, "patients": [], "do_not_retry": True},
                )
            return ToolResult(
                id=call_id,
                name=self.name,
                success=True,
                data={
                    "count": len(patients),
                    "patients": patients,
                    "note": (
                        "Speak ONLY these patients. Never invent extra names or UMR."
                    ),
                },
            )
        except httpx.HTTPError as exc:
            return ToolResult(
                id=call_id,
                name=self.name,
                success=False,
                error=hms_error_message(exc),
            )


class CreatePatientHandler(ToolHandler):
    name = "createPatient"
    description = (
        "Register a new OP patient. HMS requires name, gender, age, phone. "
        "Ask for any missing field before calling."
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
        # Normalize aliases
        if arguments.get("mobile") and not arguments.get("phone"):
            arguments = {**arguments, "phone": arguments["mobile"]}

        missing = require_fields(
            arguments,
            {
                "name": "patient name",
                "phone": "phone number",
                "gender": "gender (male/female/other)",
                "age": "age in years",
            },
        )
        if missing:
            if missing[0] == "phone":
                payload = phone_missing_payload(session)
                payload["missing"] = missing
                return ToolResult(
                    id=call_id,
                    name=self.name,
                    success=False,
                    error=phone_missing_error(session),
                    data=payload,
                )
            hints = {
                "name": "మీ పేరు చెప్తారా? / What is the patient name?",
                "gender": "gender అడగండి (male/female)",
                "age": "వయసు అడగండి",
            }
            ask = hints.get(missing[0], "Ask for the missing detail.")
            return ToolResult(
                id=call_id,
                name=self.name,
                success=False,
                error=f"Missing required fields: {', '.join(missing)}. {ask}",
                data={"missing": missing, "do_not_retry": True},
            )

        try:
            age = arguments["age"]
            if isinstance(age, str) and age.isdigit():
                age = int(age)
            body = {
                "name": str(arguments["name"]).strip(),
                "phone": str(arguments["phone"]).strip(),
                "gender": str(arguments["gender"]).strip(),
                "age": age,
                "patient_type": arguments.get("patient_type") or "OP",
                "active": True,
            }
            data = await self._hms.post(tenant, endpoints.PATIENTS, json=body)
            slim = slim_patients([data] if isinstance(data, dict) else data)
            session.tool_context["last_patients"] = slim
            return ToolResult(
                id=call_id,
                name=self.name,
                success=True,
                data={
                    "patient": slim[0] if slim else data,
                    "note": (
                        "Confirm ONLY this patient/UMR from the result. "
                        "Never invent UMR."
                    ),
                },
            )
        except httpx.HTTPError as exc:
            return ToolResult(
                id=call_id,
                name=self.name,
                success=False,
                error=hms_error_message(exc),
            )
