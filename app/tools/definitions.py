from __future__ import annotations

from typing import Any


def gemini_function_declarations() -> list[dict[str, Any]]:
    """Gemini Live tools — aligned with hms-server REST contracts."""
    return [
        {
            "name": "patientSearch",
            "description": (
                "REQUIRED before saying any patient name/UMR. "
                "Search HMS patients. Prefer phone. "
                "If phone needed: offer the calling number first "
                "(use this or another?), then read back to verify. "
                "Speak ONLY patients from the result. Never invent patients/UMR."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "phone": {"type": "string"},
                    "name": {"type": "string"},
                    "search": {"type": "string"},
                },
            },
        },
        {
            "name": "createPatient",
            "description": (
                "Register OP patient. HMS requires name, gender, age, phone. "
                "Ask one missing field at a time. For phone: offer calling number "
                "first, then verify by reading back before calling. "
                "After success, speak UMR only if returned — never invent."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "phone": {"type": "string"},
                    "gender": {"type": "string"},
                    "age": {"type": "integer"},
                },
                "required": ["name", "phone", "gender", "age"],
            },
        },
        {
            "name": "doctorAvailability",
            "description": (
                "REQUIRED before saying any doctor name or booking. "
                "Fetches live doctors from HMS GET /staff/type/Doctor. "
                "You know zero doctors until this returns. "
                "Call once (with doctorName/department filters if known), "
                "then speak ONLY names from the result. "
                "Never invent names. If empty/error, tell caller and stop — no retry loop."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "doctorName": {"type": "string"},
                    "department": {"type": "string"},
                },
            },
        },
        {
            "name": "departmentList",
            "description": (
                "REQUIRED before saying any department name. "
                "List HMS departments. Speak ONLY names from the result. "
                "Never invent departments. If empty/error, say unavailable."
            ),
            "parameters": {"type": "object", "properties": {}},
        },
        {
            "name": "bookAppointment",
            "description": (
                "Book HMS appointment. FORBIDDEN until doctorAvailability "
                "succeeded in this call. Requires name, phone, doctorName "
                "(exact name from that tool result), date YYYY-MM-DD, time. "
                "For phone: offer calling number first, then verify by reading back. "
                "Ask for any missing field — never call incomplete. "
                "Never invent doctorName. Confirm only what the API returns."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "phone": {"type": "string"},
                    "doctorName": {"type": "string"},
                    "doctorId": {"type": "string"},
                    "date": {"type": "string"},
                    "time": {"type": "string"},
                    "notes": {"type": "string"},
                },
                "required": ["name", "phone", "doctorName", "date", "time"],
            },
        },
        {
            "name": "cancelAppointment",
            "description": (
                "Cancel appointment (soft status=cancelled). "
                "Need appointmentId or phone (+ optional date). "
                "For phone: offer calling number first, then verify. "
                "Confirm cancel only from tool result — never invent appointments."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "appointmentId": {"type": "string"},
                    "phone": {"type": "string"},
                    "date": {"type": "string"},
                },
            },
        },
        {
            "name": "labReports",
            "description": (
                "REQUIRED before saying any lab/report status. "
                "Lab/diagnostics receipts from HMS. Need phone or UMR. "
                "Speak ONLY receipt fields from the result — never invent reports."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "phone": {"type": "string"},
                    "umr": {"type": "string"},
                    "patientId": {
                        "type": "string",
                        "description": "UMRNo (same as umr)",
                    },
                },
            },
        },
        {
            "name": "generateBill",
            "description": (
                "REQUIRED before saying any bill/balance. "
                "Interim bill via HMS patients/:UMR/interim-bill. "
                "Need UMR or phone. Speak ONLY amounts from the result — never invent."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "umr": {"type": "string"},
                    "patientId": {"type": "string", "description": "UMRNo"},
                    "phone": {"type": "string"},
                    "endDate": {"type": "string"},
                },
            },
        },
        {
            "name": "sendWhatsapp",
            "description": (
                "Send prescription WhatsApp only. Needs UMR + prescriptionId "
                "from prior tool results — never invent IDs. "
                "Not for free-text messages. Ask if missing."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "umr": {"type": "string"},
                    "patientId": {"type": "string", "description": "UMRNo"},
                    "prescriptionId": {"type": "string"},
                },
            },
        },
        {
            "name": "transferCall",
            "description": (
                "Transfer to the hospital's human receptionist. "
                "Omit destination unless you have an explicit E.164 phone number; "
                "do not pass labels like 'receptionist'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string"},
                    "destination": {
                        "type": "string",
                        "description": (
                            "Optional E.164 number (e.g. +919876543210). "
                            "Usually omit — the hospital transfer number is used."
                        ),
                    },
                },
            },
        },
    ]
