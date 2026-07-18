from __future__ import annotations

from typing import Any
from urllib.parse import quote

import httpx

from app.core.config import Settings
from app.core.logging import get_logger
from app.domain.models import Tenant

logger = get_logger(__name__)


class PlivoOutboundService:
    """Plivo REST helpers for outbound dial and live call transfer."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings
        self._client: httpx.AsyncClient | None = None

    async def start(self) -> None:
        self._client = httpx.AsyncClient(
            timeout=httpx.Timeout(15.0),
            auth=(self._settings.plivo_auth_id, self._settings.plivo_auth_token),
            base_url=f"https://api.plivo.com/v1/Account/{self._settings.plivo_auth_id}/",
        )

    async def stop(self) -> None:
        if self._client is not None:
            await self._client.aclose()
            self._client = None

    async def create_call(
        self,
        *,
        from_number: str,
        to_number: str,
        answer_url: str,
        hangup_url: str | None = None,
    ) -> dict[str, Any]:
        if self._client is None:
            raise RuntimeError("PlivoOutboundService not started")
        if not self._settings.plivo_auth_id or not self._settings.plivo_auth_token:
            raise RuntimeError("Plivo credentials not configured")
        payload = {
            "from": from_number,
            "to": to_number,
            "answer_url": answer_url,
            "answer_method": "POST",
            "hangup_url": hangup_url or self._settings.plivo_hangup_url or answer_url,
            "hangup_method": "POST",
        }
        response = await self._client.post("Call/", json=payload)
        response.raise_for_status()
        data = response.json()
        logger.info("outbound_call_created", to=to_number, from_number=from_number)
        return data

    async def transfer_call(
        self,
        *,
        call_uuid: str,
        destination: str,
        caller_id: str | None = None,
    ) -> dict[str, Any]:
        """
        Transfer the aleg to Dial XML that connects the human receptionist.

        Uses Plivo Call Transfer API. If your account requires a different flow,
        consult Plivo docs and adjust here — do not invent undocumented fields.
        """
        if self._client is None:
            raise RuntimeError("PlivoOutboundService not started")
        transfer_url = (
            self._settings.public_base_url.rstrip("/")
            + f"/plivo/transfer-xml?to={quote(destination)}"
        )
        # Plivo Transfer API is POST /Call/{call_uuid}/ (not .../Transfer/).
        # See https://www.plivo.com/docs/voice/api/calls/#transfer-a-call
        response = await self._client.post(
            f"Call/{call_uuid}/",
            json={
                "legs": "aleg",
                "aleg_url": transfer_url,
                "aleg_method": "GET",
            },
        )
        response.raise_for_status()
        logger.info(
            "call_transferred",
            call_uuid=call_uuid,
            destination=destination,
            caller_id=caller_id,
        )
        return response.json()

    def default_from_for_tenant(self, tenant: Tenant) -> str | None:
        return tenant.plivo_numbers[0] if tenant.plivo_numbers else None
