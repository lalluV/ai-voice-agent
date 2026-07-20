from __future__ import annotations

from typing import Any

import httpx

from app.domain.enums import CallDirection
from app.domain.models import CallSession, _normalize_phone


def hms_error_message(exc: BaseException) -> str:
    if isinstance(exc, httpx.HTTPStatusError):
        try:
            payload = exc.response.json()
            if isinstance(payload, dict):
                msg = payload.get("message") or payload.get("error")
                if msg:
                    return str(msg)
        except Exception:
            pass
        text = (exc.response.text or "").strip()
        if text:
            return text[:400]
        return f"HMS HTTP {exc.response.status_code}"
    return str(exc)


def missing_fields_result(
    *,
    call_id: str,
    name: str,
    missing: list[str],
    ask: str,
) -> dict[str, Any]:
    """Shape used inside ToolResult data/error for the voice model."""
    return {
        "missing": missing,
        "ask": ask,
        "error": (
            f"Missing required fields: {', '.join(missing)}. {ask}"
        ),
    }


def require_fields(
    arguments: dict[str, Any], required: dict[str, str]
) -> list[str]:
    """
    required: field_name -> human hint
    Returns list of missing field names.
    """
    missing: list[str] = []
    for field, _hint in required.items():
        value = arguments.get(field)
        if value is None or (isinstance(value, str) and not value.strip()):
            missing.append(field)
    return missing


def slim_patient(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "umr": doc.get("UMRNo") or doc.get("umr"),
        "name": doc.get("name"),
        "phone": doc.get("phone") or doc.get("mobile"),
        "gender": doc.get("gender"),
        "age": doc.get("age"),
        "patient_type": doc.get("patient_type"),
    }


def slim_patients(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, dict):
        items = raw.get("patients") or raw.get("data") or []
    elif isinstance(raw, list):
        items = raw
    else:
        items = []
    return [slim_patient(p) for p in items if isinstance(p, dict)][:10]


def slim_receipt(doc: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(doc.get("_id") or doc.get("id") or ""),
        "receiptId": doc.get("receiptId"),
        "patientId": doc.get("patientId"),
        "patientName": doc.get("patientName"),
        "status": doc.get("status") or doc.get("paymentStatus"),
        "type": doc.get("type"),
        "totalAmount": doc.get("totalAmount"),
        "createdAt": str(doc.get("createdAt") or ""),
    }


def slim_receipts(raw: Any) -> list[dict[str, Any]]:
    if isinstance(raw, dict):
        items = raw.get("receipts") or raw.get("data") or []
    elif isinstance(raw, list):
        items = raw
    else:
        items = []
    return [slim_receipt(r) for r in items if isinstance(r, dict)][:10]


def normalize_doctor_list(raw: Any) -> list[dict[str, str]]:
    if isinstance(raw, dict):
        raw = raw.get("staff") or raw.get("data") or raw.get("doctors") or []
    if not isinstance(raw, list):
        return []
    out: list[dict[str, str]] = []
    for item in raw:
        if not isinstance(item, dict):
            continue
        name = (
            item.get("name")
            or item.get("fullName")
            or item.get("doctorName")
            or ""
        )
        name = str(name).strip()
        if not name:
            continue
        if item.get("active") is False:
            continue
        doc_id = str(
            item.get("_id")
            or item.get("id")
            or item.get("employeeId")
            or item.get("doctorId")
            or ""
        )
        dept = str(item.get("department") or item.get("specialization") or "")
        out.append({"id": doc_id, "name": name, "department": dept})
    return out


def resolve_doctor(
    doctors: list[dict[str, str]],
    *,
    doctor_name: str = "",
    doctor_id: str | None = None,
) -> dict[str, Any]:
    if doctor_id:
        for d in doctors:
            if d.get("id") and d["id"] == doctor_id:
                return {"status": "ok", "doctor": d}

    hint = doctor_name.strip().lower()
    if not hint:
        return {"status": "not_found"}

    for prefix in ("dr.", "dr ", "doctor "):
        if hint.startswith(prefix):
            hint = hint[len(prefix) :].strip()

    exact = [d for d in doctors if d["name"].lower() == hint]
    if len(exact) == 1:
        return {"status": "ok", "doctor": exact[0]}
    if len(exact) > 1:
        return {"status": "ambiguous", "candidates": exact}

    partial = [d for d in doctors if hint in d["name"].lower()]
    if len(partial) == 1:
        return {"status": "ok", "doctor": partial[0]}
    if len(partial) > 1:
        return {"status": "ambiguous", "candidates": partial[:8]}
    return {"status": "not_found"}


def view_base_url_for_tenant(tenant: Any, origin_pattern: str) -> str:
    explicit = getattr(tenant, "hms_view_base_url", None)
    if explicit:
        return str(explicit).rstrip("/")
    return origin_pattern.format(subdomain=tenant.hms_subdomain).rstrip("/")


def customer_phone(session: CallSession) -> str | None:
    """Phone of the person on the line (inbound From / outbound To)."""
    raw = (
        session.to_number
        if session.direction == CallDirection.OUTBOUND
        else session.from_number
    )
    if not raw:
        return None
    normalized = _normalize_phone(raw)
    digits = "".join(c for c in normalized if c.isdigit())
    if len(digits) < 8:
        return None
    return normalized


def format_phone_for_speech(phone: str) -> str:
    """Group digits for natural TTS (Indian mobile → 5+5)."""
    digits = "".join(c for c in phone if c.isdigit())
    if digits.startswith("91") and len(digits) >= 12:
        digits = digits[-10:]
    elif len(digits) > 10:
        digits = digits[-10:]
    if len(digits) == 10:
        return f"{digits[:5]} {digits[5:]}"
    if len(digits) >= 6:
        mid = len(digits) // 2
        return f"{digits[:mid]} {digits[mid:]}"
    return digits or phone


def phone_missing_payload(session: CallSession) -> dict[str, Any]:
    """Tool data when phone is required — force offer/verify flow."""
    number = customer_phone(session)
    spoken = format_phone_for_speech(number) if number else None
    data: dict[str, Any] = {
        "missing": ["phone"],
        "do_not_retry": True,
    }
    if number and spoken:
        data["callerNumber"] = number
        data["callerNumberSpoken"] = spoken
        data["instruction"] = (
            f"Phone needed. First ask if they want to use this calling number "
            f"({spoken}) or another. Wait for their answer. "
            f"If they give another number, or confirm this one, read the full "
            f"number back once for verification and wait for yes. "
            f"Only then call this tool again with phone set. Do not invent digits."
        )
    else:
        data["instruction"] = (
            "Phone needed but calling number is unknown. Ask for the number, "
            "then read it back once for verification and wait for yes before "
            "calling this tool again."
        )
    return data


def phone_missing_error(session: CallSession) -> str:
    payload = phone_missing_payload(session)
    return str(payload.get("instruction") or "Ask for phone and verify it.")
