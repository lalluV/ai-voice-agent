from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import httpx
import pytest

from app.core.config import Settings
from app.domain.models import Tenant
from app.hms.client import HmsClient


@pytest.mark.asyncio
async def test_hms_client_sends_auth_headers(sample_tenant_dict: dict) -> None:
    tenant = Tenant.model_validate(sample_tenant_dict)
    client = HmsClient(Settings())
    await client.start()
    assert client._client is not None

    mock_response = MagicMock()
    mock_response.status_code = 200
    mock_response.content = b'[{"name":"ENT"}]'
    mock_response.json.return_value = [{"name": "ENT"}]
    mock_response.raise_for_status = MagicMock()

    client._client.request = AsyncMock(return_value=mock_response)  # type: ignore[method-assign]
    try:
        data = await client.get(tenant, "/departments")
        assert data[0]["name"] == "ENT"
        call_kwargs = client._client.request.await_args.kwargs
        assert call_kwargs["headers"]["x-auth-token"] == "jwt-token"
        assert "demo.healeka.com" in call_kwargs["headers"]["Origin"]
    finally:
        await client.stop()


@pytest.mark.asyncio
async def test_hms_client_raises_on_http_error(sample_tenant_dict: dict) -> None:
    tenant = Tenant.model_validate(sample_tenant_dict)
    client = HmsClient(Settings())
    await client.start()
    request = httpx.Request("GET", "https://hms.example.com/api/patients")
    response = httpx.Response(500, request=request, text="boom")
    client._client.request = AsyncMock(  # type: ignore[union-attr]
        side_effect=httpx.HTTPStatusError("err", request=request, response=response)
    )
    with pytest.raises(httpx.HTTPStatusError):
        await client.get(tenant, "/patients")
    await client.stop()
