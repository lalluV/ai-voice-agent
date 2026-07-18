from __future__ import annotations

from typing import Any

import httpx

from app.core.config import Settings
from app.core.logging import get_logger
from app.core.metrics import ERRORS
from app.domain.models import Tenant

logger = get_logger(__name__)


class HmsClient:
    """Async HMS REST client with connection pooling. Never talks to HMS DB."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: httpx.AsyncClient | None = None

    async def start(self) -> None:
        limits = httpx.Limits(
            max_connections=self._settings.hms_http_max_connections,
            max_keepalive_connections=40,
        )
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(self._settings.hms_http_timeout_seconds),
            limits=limits,
            headers={"Accept": "application/json"},
        )
        logger.info("hms_client_started")

    async def stop(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None
            logger.info("hms_client_stopped")

    def _headers(self, tenant: Tenant) -> dict[str, str]:
        origin = self._settings.hms_origin_host_pattern.format(
            subdomain=tenant.hms_subdomain
        )
        return {
            "x-auth-token": tenant.hms_auth_token,
            "Origin": origin,
            "Content-Type": "application/json",
        }

    def _url(self, tenant: Tenant, path: str) -> str:
        base = tenant.hms_base_url.rstrip("/")
        if not path.startswith("/"):
            path = "/" + path
        return f"{base}{path}"

    async def request(
        self,
        tenant: Tenant,
        method: str,
        path: str,
        *,
        params: dict[str, Any] | None = None,
        json: dict[str, Any] | None = None,
    ) -> Any:
        if self._client is None:
            raise RuntimeError("HmsClient not started")
        url = self._url(tenant, path)
        try:
            response = await self._client.request(
                method,
                url,
                params=params,
                json=json,
                headers=self._headers(tenant),
            )
            response.raise_for_status()
            if response.status_code == 204 or not response.content:
                return None
            return response.json()
        except httpx.HTTPStatusError as exc:
            ERRORS.labels(component="hms").inc()
            body = exc.response.text[:500]
            logger.error(
                "hms_http_error",
                status=exc.response.status_code,
                path=path,
                tenant_id=tenant.tenant_id,
                body=body,
            )
            raise
        except httpx.HTTPError:
            ERRORS.labels(component="hms").inc()
            logger.exception("hms_request_failed", path=path, tenant_id=tenant.tenant_id)
            raise

    async def get(
        self, tenant: Tenant, path: str, *, params: dict[str, Any] | None = None
    ) -> Any:
        return await self.request(tenant, "GET", path, params=params)

    async def post(
        self, tenant: Tenant, path: str, *, json: dict[str, Any] | None = None
    ) -> Any:
        return await self.request(tenant, "POST", path, json=json)

    async def put(
        self, tenant: Tenant, path: str, *, json: dict[str, Any] | None = None
    ) -> Any:
        return await self.request(tenant, "PUT", path, json=json)

    async def delete(self, tenant: Tenant, path: str) -> Any:
        return await self.request(tenant, "DELETE", path)
