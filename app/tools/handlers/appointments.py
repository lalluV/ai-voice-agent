from __future__ import annotations

from typing import Any

import httpx

from app.domain.models import CallSession, Tenant, ToolResult
from app.hms import endpoints
from app.hms.client import HmsClient
from app.tools.base import ToolHandler
from app.tools.helpers import (
    hms_error_message,
    normalize_doctor_list,
    resolve_doctor,
)


class BookAppointmentHandler(ToolHandler):
    name = "bookAppointment"
    description = (
        "Book an appointment ONLY after collecting patient name, phone, doctor, date, and time. "
        "Call doctorAvailability first to resolve the doctor."
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
        name = (arguments.get("name") or "").strip()
        phone = (arguments.get("phone") or arguments.get("mobile") or "").strip()
        doctor_hint = (
            arguments.get("doctor")
            or arguments.get("doctorName")
            or ""
        ).strip()
        doctor_id = (arguments.get("doctorId") or "").strip() or None
        date = (arguments.get("date") or "").strip()
        time_slot = (arguments.get("time") or "").strip()

        missing: list[str] = []
        if not name:
            missing.append("name")
        if not phone:
            missing.append("phone")
        if not doctor_hint and not doctor_id:
            missing.append("doctorName")
        if not date:
            missing.append("date")
        if not time_slot:
            missing.append("time")
        if missing:
            return ToolResult(
                id=call_id,
                name=self.name,
                success=False,
                error=(
                    "Missing required fields: "
                    + ", ".join(missing)
                    + ". Ask the caller for these one at a time, then call doctorAvailability "
                    "to confirm the doctor before booking."
                ),
                data={"missing": missing},
            )

        try:
            staff = await self._hms.get(
                tenant, endpoints.STAFF_BY_TYPE.format(staff_type="Doctor")
            )
            doctors = normalize_doctor_list(staff)
            matched = resolve_doctor(
                doctors, doctor_name=doctor_hint, doctor_id=doctor_id
            )
            if matched.get("status") == "ambiguous":
                return ToolResult(
                    id=call_id,
                    name=self.name,
                    success=False,
                    error=(
                        "Multiple doctors matched. Ask the caller which one, "
                        "then retry with the exact doctor name."
                    ),
                    data={"candidates": matched.get("candidates", [])},
                )
            if matched.get("status") == "not_found":
                return ToolResult(
                    id=call_id,
                    name=self.name,
                    success=False,
                    error=(
                        f"Doctor '{doctor_hint or doctor_id}' not found. "
                        "Call doctorAvailability, tell the caller available doctors, "
                        "and ask them to choose."
                    ),
                    data={"doctors": doctors[:15]},
                )

            doctor = matched["doctor"]
            doctor_name = doctor["name"]
            body = {
                "name": name,
                "phone": phone,
                "mobile": phone,
                # HMS Appointment schema requires `doctor` (string)
                "doctor": doctor_name,
                "doctorName": doctor_name,
                "doctorId": doctor.get("id") or doctor_id,
                "appointmentDate": date,
                "slotDate": date,
                "time": time_slot,
                "slotTime": time_slot,
                "notes": arguments.get("notes"),
                "status": "scheduled",
            }
            data = await self._hms.post(tenant, endpoints.APPOINTMENTS, json=body)
            session.tool_context["last_appointment"] = {
                "doctor": doctor_name,
                "date": date,
                "time": time_slot,
                "name": name,
                "phone": phone,
            }
            return ToolResult(
                id=call_id,
                name=self.name,
                success=True,
                data={"appointment": data, "doctor": doctor_name},
            )
        except httpx.HTTPError as exc:
            return ToolResult(
                id=call_id,
                name=self.name,
                success=False,
                error=hms_error_message(exc),
            )


class CancelAppointmentHandler(ToolHandler):
    name = "cancelAppointment"
    description = "Cancel an appointment"
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
        appointment_id = arguments.get("appointmentId")
        try:
            if not appointment_id:
                phone = arguments.get("phone")
                date = arguments.get("date")
                if not phone:
                    return ToolResult(
                        id=call_id,
                        name=self.name,
                        success=False,
                        error="Need appointmentId or phone (+ optional date). Ask the caller.",
                    )
                listing = await self._hms.get(
                    tenant,
                    endpoints.APPOINTMENTS,
                    params={"search": phone, "startDate": date, "endDate": date},
                )
                appointments = (
                    listing.get("appointments", listing)
                    if isinstance(listing, dict)
                    else listing
                )
                if not appointments:
                    return ToolResult(
                        id=call_id,
                        name=self.name,
                        success=False,
                        error="No matching appointment found",
                    )
                first = appointments[0]
                appointment_id = first.get("_id") or first.get("id")
            try:
                data = await self._hms.put(
                    tenant,
                    endpoints.APPOINTMENT_BY_ID.format(appointment_id=appointment_id),
                    json={"status": "cancelled"},
                )
            except httpx.HTTPError:
                data = await self._hms.delete(
                    tenant,
                    endpoints.APPOINTMENT_BY_ID.format(appointment_id=appointment_id),
                )
            return ToolResult(id=call_id, name=self.name, success=True, data=data)
        except httpx.HTTPError as exc:
            return ToolResult(
                id=call_id,
                name=self.name,
                success=False,
                error=hms_error_message(exc),
            )
