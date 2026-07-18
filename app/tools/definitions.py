from __future__ import annotations

from typing import Any


def gemini_function_declarations() -> list[dict[str, Any]]:
    """Gemini Live tools — aligned with hms-server REST contracts."""
    return [
        {
            "name": "patientSearch",
            "description": (
                "Search HMS patients. Prefer phone. "
                "Ask for phone or name if missing. Do not guess."
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
                "Ask one missing field at a time before calling."
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
                "List doctors from HMS staff (type Doctor). "
                "ALWAYS call before bookAppointment if doctor not confirmed."
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
            "description": "List HMS departments. Use when caller asks for departments.",
            "parameters": {"type": "object", "properties": {}},
        },
        {
            "name": "bookAppointment",
            "description": (
                "Book HMS appointment. Requires name, phone, doctorName "
                "(from doctorAvailability), date YYYY-MM-DD, time. "
                "Ask for any missing field — never call incomplete."
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
                "Need appointmentId or phone (+ optional date). Ask if missing."
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
                "Lab/diagnostics receipts from HMS. Need phone or UMR. Ask if missing."
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
                "Interim bill via HMS patients/:UMR/interim-bill. "
                "Need UMR or phone. Ask if missing."
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
                "Send prescription WhatsApp only. Needs UMR + prescriptionId. "
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
            "description": "Transfer to human receptionist when needed.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string"},
                    "destination": {"type": "string"},
                },
            },
        },
    ]
