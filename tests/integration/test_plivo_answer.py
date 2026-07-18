from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api import plivo_webhooks
from app.domain.models import CallSession, Tenant
from app.domain.enums import CallDirection


@pytest.mark.asyncio
async def test_answer_returns_stream_xml(sample_tenant_dict: dict) -> None:
    app = FastAPI()
    app.include_router(plivo_webhooks.router)

    tenant = Tenant.model_validate(sample_tenant_dict)
    session = CallSession(tenant_id=tenant.tenant_id, direction=CallDirection.INBOUND)

    resolver = AsyncMock()
    resolver.resolve_inbound = AsyncMock(return_value=tenant)
    sessions = AsyncMock()
    sessions.get_by_call_id = MagicMock(return_value=None)
    sessions.create = AsyncMock(return_value=session)

    app.state.tenant_resolver = resolver
    app.state.session_manager = sessions

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/plivo/answer",
            data={
                "CallUUID": "call-1",
                "From": "+911111111111",
                "To": "+919876543210",
                "Direction": "inbound",
            },
        )
    assert resp.status_code == 200
    assert "application/xml" in resp.headers["content-type"]
    assert "<Stream" in resp.text
    assert 'bidirectional="true"' in resp.text
    assert 'noiseCancellation="true"' in resp.text
    assert session.session_id in resp.text
    assert tenant.tenant_id in resp.text


@pytest.mark.asyncio
async def test_answer_reuses_prewarmed_outbound_session(
    sample_tenant_dict: dict,
) -> None:
    app = FastAPI()
    app.include_router(plivo_webhooks.router)

    tenant = Tenant.model_validate(sample_tenant_dict)
    session = CallSession(
        tenant_id=tenant.tenant_id,
        direction=CallDirection.OUTBOUND,
        call_id="out-call-1",
    )

    resolver = AsyncMock()
    resolver.resolve_outbound = AsyncMock(return_value=tenant)
    sessions = AsyncMock()
    sessions.get_by_call_id = MagicMock(return_value=session)
    sessions.update = AsyncMock(return_value=None)
    sessions.create = AsyncMock()

    app.state.tenant_resolver = resolver
    app.state.session_manager = sessions

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/plivo/answer",
            data={
                "CallUUID": "out-call-1",
                "From": "+919876543210",
                "To": "+911111111111",
                "Direction": "outbound",
            },
        )
    assert resp.status_code == 200
    assert session.session_id in resp.text
    sessions.create.assert_not_called()
    sessions.update.assert_awaited()
    resolver.resolve_outbound.assert_awaited()


@pytest.mark.asyncio
async def test_answer_unknown_tenant() -> None:
    app = FastAPI()
    app.include_router(plivo_webhooks.router)
    resolver = AsyncMock()
    resolver.resolve_inbound = AsyncMock(return_value=None)
    app.state.tenant_resolver = resolver
    app.state.session_manager = MagicMock()

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        resp = await client.post(
            "/plivo/answer",
            data={"To": "+910000000000", "From": "+911", "CallUUID": "x"},
        )
    assert resp.status_code == 200
    assert "not configured" in resp.text
