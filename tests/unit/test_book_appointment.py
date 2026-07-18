from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.domain.models import CallSession, Tenant
from app.tools.handlers.appointments import BookAppointmentHandler
from app.tools.helpers import normalize_doctor_list, resolve_doctor


def test_resolve_doctor_partial() -> None:
    doctors = [
        {"id": "1", "name": "Dr Ravi Kumar", "department": "ENT"},
        {"id": "2", "name": "Dr Sita", "department": "Ortho"},
    ]
    result = resolve_doctor(doctors, doctor_name="ravi")
    assert result["status"] == "ok"
    assert result["doctor"]["id"] == "1"


def test_normalize_doctor_list() -> None:
    raw = [{"_id": "abc", "name": "Dr Rao", "department": "General"}]
    out = normalize_doctor_list(raw)
    assert out[0]["id"] == "abc"
    assert out[0]["name"] == "Dr Rao"


@pytest.mark.asyncio
async def test_book_requires_fields(sample_tenant_dict: dict) -> None:
    handler = BookAppointmentHandler(AsyncMock())
    tenant = Tenant.model_validate(sample_tenant_dict)
    session = CallSession(tenant_id=tenant.tenant_id)
    result = await handler.execute(
        tenant=tenant,
        session=session,
        arguments={"name": "Ravi"},
        call_id="c1",
    )
    assert not result.success
    assert "Missing required fields" in (result.error or "")
    assert "doctorName" in result.data["missing"]


@pytest.mark.asyncio
async def test_book_sends_doctor_field(sample_tenant_dict: dict) -> None:
    hms = AsyncMock()
    hms.get = AsyncMock(
        return_value=[{"_id": "d1", "name": "Dr Ravi Kumar", "department": "ENT"}]
    )
    hms.post = AsyncMock(return_value={"_id": "appt1", "status": "scheduled"})
    handler = BookAppointmentHandler(hms)
    tenant = Tenant.model_validate(sample_tenant_dict)
    session = CallSession(tenant_id=tenant.tenant_id)
    result = await handler.execute(
        tenant=tenant,
        session=session,
        arguments={
            "name": "Patient One",
            "phone": "9000000000",
            "doctorName": "Ravi",
            "date": "2026-07-20",
            "time": "10:00",
        },
        call_id="c2",
    )
    assert result.success
    body = hms.post.await_args.kwargs["json"]
    assert body["doctor"] == "Dr Ravi Kumar"
    assert body["doctorName"] == "Dr Ravi Kumar"
