from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.core.config import Settings
from app.domain.models import CallSession, Tenant
from app.tools.handlers.hospital import GenerateBillHandler, SendWhatsappHandler
from app.tools.handlers.patient import CreatePatientHandler, PatientSearchHandler


@pytest.mark.asyncio
async def test_patient_search_requires_query(sample_tenant_dict: dict) -> None:
    handler = PatientSearchHandler(AsyncMock())
    tenant = Tenant.model_validate(sample_tenant_dict)
    session = CallSession(tenant_id=tenant.tenant_id)
    result = await handler.execute(
        tenant=tenant, session=session, arguments={}, call_id="c1"
    )
    assert not result.success
    assert "phone" in result.data["missing"]


@pytest.mark.asyncio
async def test_create_patient_requires_fields(sample_tenant_dict: dict) -> None:
    handler = CreatePatientHandler(AsyncMock())
    tenant = Tenant.model_validate(sample_tenant_dict)
    session = CallSession(tenant_id=tenant.tenant_id)
    result = await handler.execute(
        tenant=tenant,
        session=session,
        arguments={"name": "Ravi"},
        call_id="c1",
    )
    assert not result.success
    assert "phone" in result.data["missing"]
    assert "gender" in result.data["missing"]


@pytest.mark.asyncio
async def test_create_patient_posts_required_body(sample_tenant_dict: dict) -> None:
    hms = AsyncMock()
    hms.post = AsyncMock(
        return_value={
            "name": "Ravi",
            "phone": "900",
            "gender": "male",
            "age": 30,
            "UMRNo": "UMR123",
        }
    )
    handler = CreatePatientHandler(hms)
    tenant = Tenant.model_validate(sample_tenant_dict)
    session = CallSession(tenant_id=tenant.tenant_id)
    result = await handler.execute(
        tenant=tenant,
        session=session,
        arguments={
            "name": "Ravi",
            "phone": "900",
            "gender": "male",
            "age": 30,
        },
        call_id="c1",
    )
    assert result.success
    body = hms.post.await_args.kwargs["json"]
    assert body["name"] == "Ravi"
    assert body["patient_type"] == "OP"


@pytest.mark.asyncio
async def test_generate_bill_asks_for_id(sample_tenant_dict: dict) -> None:
    handler = GenerateBillHandler(AsyncMock())
    tenant = Tenant.model_validate(sample_tenant_dict)
    session = CallSession(tenant_id=tenant.tenant_id)
    result = await handler.execute(
        tenant=tenant, session=session, arguments={}, call_id="c1"
    )
    assert not result.success
    assert "missing" in result.data


@pytest.mark.asyncio
async def test_whatsapp_requires_umr_and_rx(sample_tenant_dict: dict) -> None:
    handler = SendWhatsappHandler(AsyncMock(), Settings())
    tenant = Tenant.model_validate(sample_tenant_dict)
    session = CallSession(tenant_id=tenant.tenant_id)
    result = await handler.execute(
        tenant=tenant,
        session=session,
        arguments={"phone": "999", "message": "hi"},
        call_id="c1",
    )
    assert not result.success
    assert "prescriptionId" in result.data["missing"]


@pytest.mark.asyncio
async def test_whatsapp_sends_view_base_url(sample_tenant_dict: dict) -> None:
    hms = AsyncMock()
    hms.post = AsyncMock(return_value={"success": True})
    handler = SendWhatsappHandler(hms, Settings())
    tenant = Tenant.model_validate(sample_tenant_dict)
    session = CallSession(tenant_id=tenant.tenant_id)
    result = await handler.execute(
        tenant=tenant,
        session=session,
        arguments={"umr": "UMR1", "prescriptionId": "rx1"},
        call_id="c1",
    )
    assert result.success
    assert hms.post.await_args.kwargs["json"]["viewBaseUrl"]
