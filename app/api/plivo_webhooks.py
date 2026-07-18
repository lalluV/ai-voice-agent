from __future__ import annotations

import html

from fastapi import APIRouter, Depends, Query, Request, Response
from fastapi.responses import PlainTextResponse

from app.core.config import Settings, get_settings
from app.core.logging import get_logger
from app.core.security import require_admin_api_key, validate_plivo_request
from app.domain.enums import CallDirection, CallEndReason
from app.domain.models import OutboundCallRequest
from app.tenants.resolver import TenantResolver

logger = get_logger(__name__)

router = APIRouter(tags=["plivo"])


def _xml_response(xml: str) -> Response:
    return Response(content=xml, media_type="application/xml")


@router.post("/plivo/answer")
async def plivo_answer(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> Response:
    params = await validate_plivo_request(request, settings)
    call_uuid = params.get("CallUUID")
    from_number = params.get("From")
    to_number = params.get("To")
    direction_raw = params.get("Direction")

    resolver: TenantResolver = request.app.state.tenant_resolver
    sessions = request.app.state.session_manager

    direction = (
        CallDirection.OUTBOUND
        if (direction_raw or "").lower() == "outbound"
        else CallDirection.INBOUND
    )
    if direction == CallDirection.INBOUND:
        tenant = await resolver.resolve_inbound(to_number)
    else:
        tenant = await resolver.resolve_outbound(from_number)

    if tenant is None:
        logger.error("answer_unknown_tenant", to=to_number, from_number=from_number)
        return _xml_response(
            '<?xml version="1.0" encoding="UTF-8"?>'
            "<Response><Speak>Sorry, this number is not configured.</Speak><Hangup/></Response>"
        )

    session = await sessions.create(
        tenant_id=tenant.tenant_id,
        direction=direction,
        from_number=from_number,
        to_number=to_number,
        call_id=call_uuid,
        metadata={"plivo_direction": direction_raw},
    )

    ws_url = settings.public_ws_base_url.rstrip("/") + "/ws/plivo/stream"
    extra = f"tenantId={tenant.tenant_id};sessionId={session.session_id}"
    content_type = settings.plivo_audio_content_type
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Stream bidirectional="true" keepCallAlive="true" contentType="{content_type}" extraHeaders="{extra}">
    {ws_url}
  </Stream>
</Response>"""
    logger.info(
        "answer_xml_returned",
        session_id=session.session_id,
        tenant_id=tenant.tenant_id,
        call_uuid=call_uuid,
    )
    return _xml_response(xml)


@router.post("/plivo/hangup")
async def plivo_hangup(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> Response:
    params = await validate_plivo_request(request, settings)
    call_uuid = params.get("CallUUID")
    sessions = request.app.state.session_manager
    orchestrator = request.app.state.orchestrator
    session = sessions.get_by_call_id(call_uuid) if call_uuid else None
    if session:
        await orchestrator.end_stream(session.session_id, reason=CallEndReason.HANGUP)
    return PlainTextResponse("OK")


@router.post("/plivo/stream-status")
async def plivo_stream_status(
    request: Request,
    settings: Settings = Depends(get_settings),
) -> Response:
    params = await validate_plivo_request(request, settings)
    logger.info("plivo_stream_status", **params)
    return PlainTextResponse("OK")


@router.get("/plivo/transfer-xml")
async def transfer_xml(to: str = Query(...)) -> Response:
    """XML endpoint used by Plivo Transfer aleg_url."""
    safe = html.escape(to, quote=True)
    xml = f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Dial>
    <Number>{safe}</Number>
  </Dial>
</Response>"""
    return _xml_response(xml)


@router.post("/calls/outbound", dependencies=[Depends(require_admin_api_key)])
async def create_outbound_call(
    payload: OutboundCallRequest,
    request: Request,
    settings: Settings = Depends(get_settings),
) -> dict:
    tenant_repo = request.app.state.tenant_repo
    plivo = request.app.state.plivo_service
    tenant = await tenant_repo.get(payload.tenant_id)
    if not tenant or not tenant.enabled:
        return {"success": False, "error": "Tenant not found or disabled"}
    from_number = payload.from_number or (
        tenant.plivo_numbers[0] if tenant.plivo_numbers else None
    )
    if not from_number:
        return {"success": False, "error": "No from_number configured"}
    answer_url = payload.answer_url or (
        settings.plivo_answer_url
        or settings.public_base_url.rstrip("/") + "/plivo/answer"
    )
    hangup_url = (
        settings.plivo_hangup_url
        or settings.public_base_url.rstrip("/") + "/plivo/hangup"
    )
    data = await plivo.create_call(
        from_number=from_number,
        to_number=payload.to_number,
        answer_url=answer_url,
        hangup_url=hangup_url,
    )
    return {"success": True, "data": data}
