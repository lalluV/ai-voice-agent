from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from app.core.config import Settings
from app.domain.models import Tenant
from app.tenants.cache import TenantCache
from app.tenants.resolver import TenantResolver


@pytest.mark.asyncio
async def test_resolve_uses_cache(sample_tenant_dict: dict) -> None:
    tenant = Tenant.model_validate(sample_tenant_dict)
    repo = AsyncMock()
    repo.find_by_number = AsyncMock(return_value=None)
    cache = TenantCache(None, Settings(redis_enabled=False))
    cache.get = AsyncMock(return_value=tenant)  # type: ignore[method-assign]
    cache.set = AsyncMock()  # type: ignore[method-assign]
    resolver = TenantResolver(repo, cache)
    result = await resolver.resolve_by_did("+919876543210")
    assert result is not None
    assert result.tenant_id == "demo"
    repo.find_by_number.assert_not_awaited()


@pytest.mark.asyncio
async def test_resolve_falls_back_to_repo(sample_tenant_dict: dict) -> None:
    tenant = Tenant.model_validate(sample_tenant_dict)
    repo = AsyncMock()
    repo.find_by_number = AsyncMock(return_value=tenant)
    cache = TenantCache(None, Settings(redis_enabled=False))
    cache.get = AsyncMock(return_value=None)  # type: ignore[method-assign]
    cache.set = AsyncMock()  # type: ignore[method-assign]
    resolver = TenantResolver(repo, cache)
    result = await resolver.resolve_inbound("9876543210")
    assert result is not None
    assert result.tenant_id == "demo"
    assert cache.set.await_count >= 1
