from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.domain.models import CallSession, Tenant, ToolCall
from app.tools.handlers.hospital import DoctorAvailabilityHandler
from app.tools.handlers.patient import PatientSearchHandler
from app.tools.handlers.transfer import TransferCallHandler
from app.tools.router import ToolRouter


@pytest.mark.asyncio
async def test_patient_search_by_phone(sample_tenant_dict: dict) -> None:
    hms = AsyncMock()
    hms.get = AsyncMock(return_value=[{"name": "Ravi", "phone": "999", "UMRNo": "UMR1"}])
    handler = PatientSearchHandler(hms)
    tenant = Tenant.model_validate(sample_tenant_dict)
    session = CallSession(tenant_id=tenant.tenant_id)
    result = await handler.execute(
        tenant=tenant,
        session=session,
        arguments={"phone": "999"},
        call_id="c1",
    )
    assert result.success
    assert result.data["patients"][0]["name"] == "Ravi"


@pytest.mark.asyncio
async def test_doctor_availability_lists_doctors(sample_tenant_dict: dict) -> None:
    hms = AsyncMock()
    hms.get = AsyncMock(return_value=[{"name": "Dr Rao", "department": "ENT"}])
    handler = DoctorAvailabilityHandler(hms)
    tenant = Tenant.model_validate(sample_tenant_dict)
    session = CallSession(tenant_id=tenant.tenant_id)
    result = await handler.execute(
        tenant=tenant,
        session=session,
        arguments={"doctorName": "Rao"},
        call_id="c1",
    )
    assert result.success
    assert result.data["count"] == 1
    assert result.data["doctors"][0]["name"] == "Dr Rao"


@pytest.mark.asyncio
async def test_doctor_availability_empty_forbids_retry(
    sample_tenant_dict: dict,
) -> None:
    hms = AsyncMock()
    hms.get = AsyncMock(return_value=[])
    handler = DoctorAvailabilityHandler(hms)
    tenant = Tenant.model_validate(sample_tenant_dict)
    session = CallSession(tenant_id=tenant.tenant_id)
    result = await handler.execute(
        tenant=tenant, session=session, arguments={}, call_id="c1"
    )
    assert not result.success
    assert result.data["do_not_retry"] is True
    assert "invent" in (result.error or "").lower()


@pytest.mark.asyncio
async def test_tool_router_unknown() -> None:
    router = ToolRouter([])
    tenant = Tenant(
        tenant_id="x",
        name="x",
        hms_base_url="http://x",
        hms_subdomain="x",
        hms_auth_token="t",
    )
    session = CallSession(tenant_id="x")
    result = await router.execute(
        tenant=tenant,
        session=session,
        call=ToolCall(id="1", name="nope", arguments={}),
    )
    assert not result.success


@pytest.mark.asyncio
async def test_tool_router_blocks_identical_loop(sample_tenant_dict: dict) -> None:
    hms = AsyncMock()
    hms.get = AsyncMock(return_value=[])
    router = ToolRouter([DoctorAvailabilityHandler(hms)])
    tenant = Tenant.model_validate(sample_tenant_dict)
    session = CallSession(tenant_id=tenant.tenant_id)
    call = ToolCall(id="1", name="doctorAvailability", arguments={})

    first = await router.execute(tenant=tenant, session=session, call=call)
    second = await router.execute(tenant=tenant, session=session, call=call)
    third = await router.execute(tenant=tenant, session=session, call=call)

    assert not first.success
    assert not second.success
    assert not third.success
    assert third.data.get("blocked") is True
    assert hms.get.await_count == 2


@pytest.mark.asyncio
async def test_transfer_ignores_label_destination(sample_tenant_dict: dict) -> None:
    transfer_fn = AsyncMock(return_value={"status": "ok"})
    handler = TransferCallHandler(transfer_fn)
    tenant = Tenant.model_validate(sample_tenant_dict)
    session = CallSession(tenant_id=tenant.tenant_id, call_id="uuid-1")

    result = await handler.execute(
        tenant=tenant,
        session=session,
        arguments={"destination": "receptionist", "reason": "caller asked"},
        call_id="c1",
    )

    assert result.success
    transfer_fn.assert_awaited_once()
    assert transfer_fn.await_args.args[2] == "+919999999999"


@pytest.mark.asyncio
async def test_transfer_uses_explicit_e164(sample_tenant_dict: dict) -> None:
    transfer_fn = AsyncMock(return_value={"status": "ok"})
    handler = TransferCallHandler(transfer_fn)
    tenant = Tenant.model_validate(sample_tenant_dict)
    session = CallSession(tenant_id=tenant.tenant_id, call_id="uuid-1")

    result = await handler.execute(
        tenant=tenant,
        session=session,
        arguments={"destination": "+918888888888"},
        call_id="c1",
    )

    assert result.success
    assert transfer_fn.await_args.args[2] == "+918888888888"
