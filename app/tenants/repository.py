from __future__ import annotations

from datetime import datetime, timezone

from motor.motor_asyncio import AsyncIOMotorDatabase
from pymongo import ReturnDocument

from app.domain.models import Tenant, TenantCreate, TenantUpdate, _normalize_phone


class TenantRepository:
    def __init__(self, db: AsyncIOMotorDatabase) -> None:
        self._col = db.tenants

    async def create(self, payload: TenantCreate) -> Tenant:
        tenant = Tenant(**payload.model_dump())
        doc = tenant.model_dump(mode="json")
        await self._col.insert_one(doc)
        return tenant

    async def get(self, tenant_id: str) -> Tenant | None:
        doc = await self._col.find_one({"tenant_id": tenant_id}, {"_id": 0})
        return Tenant.model_validate(doc) if doc else None

    async def list(self, enabled_only: bool = False) -> list[Tenant]:
        query: dict = {}
        if enabled_only:
            query["enabled"] = True
        cursor = self._col.find(query, {"_id": 0}).sort("tenant_id", 1)
        return [Tenant.model_validate(doc) async for doc in cursor]

    async def update(self, tenant_id: str, payload: TenantUpdate) -> Tenant | None:
        updates = {k: v for k, v in payload.model_dump(exclude_unset=True).items()}
        if not updates:
            return await self.get(tenant_id)
        updates["updated_at"] = datetime.now(timezone.utc)
        result = await self._col.find_one_and_update(
            {"tenant_id": tenant_id},
            {"$set": updates},
            return_document=ReturnDocument.AFTER,
            projection={"_id": 0},
        )
        return Tenant.model_validate(result) if result else None

    async def delete(self, tenant_id: str) -> bool:
        result = await self._col.delete_one({"tenant_id": tenant_id})
        return result.deleted_count > 0

    async def find_by_number(self, phone_number: str) -> Tenant | None:
        normalized = _normalize_phone(phone_number)
        # Match exact or last-10 digits for India mobiles stored inconsistently
        candidates = {normalized, phone_number}
        if len(normalized) >= 10:
            candidates.add(normalized[-10:])
            candidates.add("+91" + normalized[-10:])
        cursor = self._col.find({"enabled": True}, {"_id": 0})
        async for doc in cursor:
            tenant = Tenant.model_validate(doc)
            numbers = tenant.normalized_numbers()
            expanded = set(numbers)
            for n in numbers:
                if len(n) >= 10:
                    expanded.add(n[-10:])
            if candidates & expanded or candidates & set(tenant.plivo_numbers):
                return tenant
        return None
