from __future__ import annotations

from typing import Any


def gemini_function_declarations() -> list[dict[str, Any]]:
    """Gemini Live-compatible function declarations."""
    return [
        {
            "name": "patientSearch",
            "description": "Search patients by phone number or name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone": {"type": "string", "description": "Patient phone number"},
                    "name": {"type": "string", "description": "Patient name search"},
                    "search": {"type": "string", "description": "Generic search text"},
                },
            },
        },
        {
            "name": "createPatient",
            "description": "Register a new patient.",
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
            "name": "bookAppointment",
            "description": "Book a patient appointment.",
            "parameters": {
                "type": "object",
                "properties": {
                    "name": {"type": "string"},
                    "phone": {"type": "string"},
                    "doctorName": {"type": "string"},
                    "doctorId": {"type": "string"},
                    "date": {"type": "string", "description": "YYYY-MM-DD"},
                    "time": {"type": "string", "description": "HH:MM or slot label"},
                    "notes": {"type": "string"},
                },
                "required": ["name", "phone", "date", "time"],
            },
        },
        {
            "name": "cancelAppointment",
            "description": "Cancel an appointment by id or by patient phone + date.",
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
            "name": "doctorAvailability",
            "description": "Get doctor directory / approximate availability signals.",
            "parameters": {
                "type": "object",
                "properties": {
                    "doctorName": {"type": "string"},
                    "department": {"type": "string"},
                    "date": {"type": "string"},
                },
            },
        },
        {
            "name": "departmentList",
            "description": "List hospital departments.",
            "parameters": {"type": "object", "properties": {}},
        },
        {
            "name": "labReports",
            "description": "Look up lab/diagnostics report information for a patient.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone": {"type": "string"},
                    "patientId": {"type": "string"},
                    "umr": {"type": "string"},
                },
            },
        },
        {
            "name": "generateBill",
            "description": "Fetch interim bill information for a patient.",
            "parameters": {
                "type": "object",
                "properties": {
                    "patientId": {"type": "string"},
                    "umr": {"type": "string"},
                    "phone": {"type": "string"},
                },
            },
        },
        {
            "name": "sendWhatsapp",
            "description": "Send a WhatsApp message when supported by HMS.",
            "parameters": {
                "type": "object",
                "properties": {
                    "phone": {"type": "string"},
                    "patientId": {"type": "string"},
                    "prescriptionId": {"type": "string"},
                    "message": {"type": "string"},
                },
            },
        },
        {
            "name": "transferCall",
            "description": "Transfer the live call to a human receptionist.",
            "parameters": {
                "type": "object",
                "properties": {
                    "reason": {"type": "string"},
                    "destination": {
                        "type": "string",
                        "description": "Optional override number",
                    },
                },
            },
        },
    ]
