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
    phone_missing_error,
    phone_missing_payload,
    resolve_doctor,
)


class BookAppointmentHandler(ToolHandler):
    name = "bookAppointment"
    description = (
        "Book an appointment ONLY after doctorAvailability in this call, "
        "and after collecting patient name, phone, doctor, date, and time. "
        "doctorName must be an exact name from doctorAvailability — never invent."
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
            if "phone" in missing and len(missing) == 1:
                payload = phone_missing_payload(session)
                return ToolResult(
                    id=call_id,
                    name=self.name,
                    success=False,
                    error=phone_missing_error(session),
                    data=payload,
                )
            return ToolResult(
                id=call_id,
                name=self.name,
                success=False,
                error=(
                    "Missing required fields: "
                    + ", ".join(missing)
                    + ". Ask the caller for these one at a time. "
                    "For phone: offer the calling number first (use this or another?), "
                    "then read it back to verify. "
                    "Do not call bookAppointment again until they answer."
                ),
                data={"missing": missing, "do_not_retry": True},
            )

        if not session.tool_context.get("doctors_fetched"):
            return ToolResult(
                id=call_id,
                name=self.name,
                success=False,
                error=(
                    "Call doctorAvailability first and wait for its result. "
                    "Do NOT invent or guess doctor names. "
                    "Then call bookAppointment with an exact doctorName from that list."
                ),
                data={
                    "missing_tool": "doctorAvailability",
                    "do_not_retry": True,
                },
            )

        try:
            doctors = session.tool_context.get("doctors_all") or session.tool_context.get(
                "doctors"
            )
            if not doctors:
                staff = await self._hms.get(
                    tenant, endpoints.STAFF_BY_TYPE.format(staff_type="Doctor")
                )
                doctors = normalize_doctor_list(staff)
                session.tool_context["doctors_all"] = doctors

            if not doctors:
                return ToolResult(
                    id=call_id,
                    name=self.name,
                    success=False,
                    error=(
                        "No doctors available in HMS. Do NOT invent a doctor name. "
                        "Tell the caller booking is unavailable and offer transfer. "
                        "Do NOT call doctorAvailability or bookAppointment again."
                    ),
                    data={"do_not_retry": True},
                )

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
                        "then wait for their answer before booking again."
                    ),
                    data={
                        "candidates": matched.get("candidates", []),
                        "do_not_retry": True,
                    },
                )
            if matched.get("status") == "not_found":
                sample = [
                    {"name": d["name"], "department": d.get("department") or ""}
                    for d in doctors[:8]
                ]
                return ToolResult(
                    id=call_id,
                    name=self.name,
                    success=False,
                    error=(
                        f"Doctor '{doctor_hint or doctor_id}' not found. "
                        "Do NOT invent names. Tell the caller 2–3 available doctors "
                        "from availableSample (if any), ask them to choose, and wait. "
                        "Do not call tools again until they answer."
                    ),
                    data={
                        "availableSample": sample,
                        "do_not_retry": True,
                    },
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
                data={
                    "appointment": data,
                    "doctor": doctor_name,
                    "note": (
                        "Booking succeeded. Confirm doctor, date, and time to the "
                        "caller now in one short sentence."
                    ),
                },
            )
        except httpx.HTTPError as exc:
            return ToolResult(
                id=call_id,
                name=self.name,
                success=False,
                error=(
                    f"{hms_error_message(exc)}. Tell the caller briefly and offer "
                    "transfer if needed. Do not keep retrying booking silently."
                ),
                data={"do_not_retry": True},
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
                    payload = phone_missing_payload(session)
                    return ToolResult(
                        id=call_id,
                        name=self.name,
                        success=False,
                        error=phone_missing_error(session),
                        data=payload,
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
