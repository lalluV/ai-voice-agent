from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.core.security import require_admin_api_key
from app.domain.models import TenantCreate, TenantPublic, TenantUpdate
from app.tenants.cache import TenantCache
from app.tenants.repository import TenantRepository

router = APIRouter(
    prefix="/admin/tenants",
    tags=["admin"],
    dependencies=[Depends(require_admin_api_key)],
)


def _repo(request: Request) -> TenantRepository:
    return request.app.state.tenant_repo


def _cache(request: Request) -> TenantCache:
    return request.app.state.tenant_cache


@router.get("", response_model=list[TenantPublic])
async def list_tenants(request: Request) -> list[TenantPublic]:
    tenants = await _repo(request).list()
    return [TenantPublic.from_tenant(t) for t in tenants]


@router.post("", response_model=TenantPublic, status_code=status.HTTP_201_CREATED)
async def create_tenant(payload: TenantCreate, request: Request) -> TenantPublic:
    existing = await _repo(request).get(payload.tenant_id)
    if existing:
        raise HTTPException(status_code=409, detail="Tenant already exists")
    tenant = await _repo(request).create(payload)
    return TenantPublic.from_tenant(tenant)


@router.get("/{tenant_id}", response_model=TenantPublic)
async def get_tenant(tenant_id: str, request: Request) -> TenantPublic:
    tenant = await _repo(request).get(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    return TenantPublic.from_tenant(tenant)


@router.patch("/{tenant_id}", response_model=TenantPublic)
async def update_tenant(
    tenant_id: str, payload: TenantUpdate, request: Request
) -> TenantPublic:
    previous = await _repo(request).get(tenant_id)
    tenant = await _repo(request).update(tenant_id, payload)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")
    if previous:
        await _cache(request).invalidate_tenant(previous)
    await _cache(request).invalidate_tenant(tenant)
    return TenantPublic.from_tenant(tenant)


@router.delete("/{tenant_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tenant(tenant_id: str, request: Request) -> None:
    previous = await _repo(request).get(tenant_id)
    deleted = await _repo(request).delete(tenant_id)
    if not deleted:
        raise HTTPException(status_code=404, detail="Tenant not found")
    if previous:
        await _cache(request).invalidate_tenant(previous)
