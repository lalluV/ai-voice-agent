from __future__ import annotations

from typing import Any

import httpx

from app.domain.models import CallSession, Tenant, ToolResult
from app.hms import endpoints
from app.hms.client import HmsClient
from app.tools.base import ToolHandler


class BookAppointmentHandler(ToolHandler):
    name = "bookAppointment"
    description = "Book an appointment"
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
            "phone": arguments.get("phone"),
            "mobile": arguments.get("phone"),
            "doctorName": arguments.get("doctorName"),
            "doctorId": arguments.get("doctorId"),
            "appointmentDate": arguments.get("date"),
            "slotDate": arguments.get("date"),
            "time": arguments.get("time"),
            "slotTime": arguments.get("time"),
            "notes": arguments.get("notes"),
            "status": "scheduled",
        }
        try:
            data = await self._hms.post(tenant, endpoints.APPOINTMENTS, json=body)
            return ToolResult(id=call_id, name=self.name, success=True, data=data)
        except httpx.HTTPError as exc:
            return ToolResult(
                id=call_id, name=self.name, success=False, error=str(exc)
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
            # Prefer status update; fall back to delete
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
                id=call_id, name=self.name, success=False, error=str(exc)
            )
