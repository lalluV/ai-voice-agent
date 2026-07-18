from __future__ import annotations

from app.core.logging import get_logger
from app.domain.models import Tenant, _normalize_phone
from app.tenants.cache import TenantCache
from app.tenants.repository import TenantRepository

logger = get_logger(__name__)


class TenantResolver:
    def __init__(self, repository: TenantRepository, cache: TenantCache) -> None:
        self._repo = repository
        self._cache = cache

    async def resolve_by_did(self, did: str | None) -> Tenant | None:
        if not did:
            return None
        normalized = _normalize_phone(did)
        cached = await self._cache.get(normalized)
        if cached and cached.enabled:
            return cached
        tenant = await self._repo.find_by_number(normalized)
        if tenant:
            await self._cache.set(normalized, tenant)
            for number in tenant.plivo_numbers:
                await self._cache.set(_normalize_phone(number), tenant)
        else:
            logger.warning("tenant_not_found_for_did", did=normalized)
        return tenant

    async def resolve_inbound(self, to_number: str | None) -> Tenant | None:
        return await self.resolve_by_did(to_number)

    async def resolve_outbound(
        self, from_number: str | None, tenant_id: str | None = None
    ) -> Tenant | None:
        if tenant_id:
            return await self._repo.get(tenant_id)
        return await self.resolve_by_did(from_number)
