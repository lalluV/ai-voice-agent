from __future__ import annotations

import base64
import hashlib
import hmac
from typing import Annotated

from fastapi import Depends, Header, HTTPException, Request, status

from app.core.config import Settings, get_settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def require_admin_api_key(
    x_admin_api_key: Annotated[str | None, Header()] = None,
    settings: Settings = Depends(get_settings),
) -> None:
    if not x_admin_api_key or not hmac.compare_digest(
        x_admin_api_key, settings.admin_api_key
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing admin API key",
        )


def compute_plivo_signature_v3(
    auth_token: str,
    nonce: str,
    method: str,
    uri: str,
    params: dict[str, str] | None = None,
) -> str:
    """
    Plivo Signature V3: Base64(HMAC-SHA256(auth_token, nonce + method + uri [+ sorted params])).
    See https://www.plivo.com/docs/voice/concepts/signature-validation/
    """
    payload = f"{nonce}{method.upper()}{uri}"
    if params:
        items = sorted((str(k), str(v)) for k, v in params.items())
        payload += "".join(f"{k}{v}" for k, v in items)
    digest = hmac.new(
        auth_token.encode("utf-8"),
        payload.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(digest).decode("utf-8")


def verify_plivo_signature(
    *,
    settings: Settings,
    signature_header: str | None,
    nonce: str | None,
    method: str,
    uri: str,
    params: dict[str, str],
) -> None:
    if not settings.plivo_validate_signature:
        return
    if not settings.plivo_auth_token:
        logger.warning("plivo_signature_skipped_missing_token")
        return
    if not signature_header or not nonce:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing Plivo signature headers",
        )

    expected = compute_plivo_signature_v3(
        settings.plivo_auth_token,
        nonce,
        method,
        uri,
        params,
    )
    candidates = [s.strip() for s in signature_header.split(",")]
    if any(hmac.compare_digest(expected, c) for c in candidates):
        return

    from urllib.parse import urlparse

    path = urlparse(uri).path
    expected_path = compute_plivo_signature_v3(
        settings.plivo_auth_token,
        nonce,
        method,
        f"{settings.public_base_url.rstrip('/')}{path}",
        params,
    )
    if any(hmac.compare_digest(expected_path, c) for c in candidates):
        return

    logger.warning("plivo_signature_invalid", uri=uri)
    raise HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Invalid Plivo signature",
    )


async def validate_plivo_request(request: Request, settings: Settings) -> dict[str, str]:
    """Read form once, validate signature, return params."""
    form = await request.form()
    params = {k: str(v) for k, v in form.items()}
    verify_plivo_signature(
        settings=settings,
        signature_header=request.headers.get("X-Plivo-Signature-V3"),
        nonce=request.headers.get("X-Plivo-Signature-V3-Nonce"),
        method=request.method,
        uri=str(request.url),
        params=params,
    )
    return params
