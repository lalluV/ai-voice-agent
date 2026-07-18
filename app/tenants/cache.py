from __future__ import annotations

import json

from redis.asyncio import Redis

from app.core.config import Settings
from app.domain.models import Tenant


class TenantCache:
    PREFIX = "voice:tenant:did:"

    def __init__(self, redis: Redis | None, settings: Settings) -> None:
        self._redis = redis
        self._ttl = settings.tenant_cache_ttl_seconds

    def _key(self, did: str) -> str:
        return f"{self.PREFIX}{did}"

    async def get(self, did: str) -> Tenant | None:
        if self._redis is None:
            return None
        raw = await self._redis.get(self._key(did))
        if not raw:
            return None
        return Tenant.model_validate(json.loads(raw))

    async def set(self, did: str, tenant: Tenant) -> None:
        if self._redis is None:
            return
        await self._redis.set(
            self._key(did),
            tenant.model_dump_json(),
            ex=self._ttl,
        )

    async def invalidate_tenant(self, tenant: Tenant) -> None:
        if self._redis is None:
            return
        if tenant.plivo_numbers:
            await self._redis.delete(*(self._key(n) for n in tenant.plivo_numbers))
