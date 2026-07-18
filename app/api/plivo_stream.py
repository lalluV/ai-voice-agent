from __future__ import annotations

import json

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.logging import get_logger
from app.core.metrics import ERRORS
from app.domain.enums import CallEndReason, SessionStatus

logger = get_logger(__name__)

router = APIRouter(tags=["plivo-stream"])


def _parse_extra_headers(raw: str | dict | None) -> dict[str, str]:
    if not raw:
        return {}
    if isinstance(raw, dict):
        return {str(k): str(v) for k, v in raw.items()}
    result: dict[str, str] = {}
    for part in str(raw).split(";"):
        part = part.strip()
        if not part or "=" not in part:
            continue
        k, v = part.split("=", 1)
        result[k.strip()] = v.strip()
    return result


@router.websocket("/ws/plivo/stream")
async def plivo_stream(websocket: WebSocket) -> None:
    app = websocket.app
    if getattr(app.state, "shutting_down", False):
        await websocket.close(code=1013)
        return

    await websocket.accept()
    sessions = app.state.session_manager
    orchestrator = app.state.orchestrator
    tenant_repo = app.state.tenant_repo

    session_id: str | None = None
    stream_id: str | None = None

    try:
        while True:
            message = await websocket.receive_text()
            data = json.loads(message)
            event = data.get("event")

            if event == "start":
                start = data.get("start") or {}
                stream_id = start.get("streamId") or data.get("streamId")
                call_id = start.get("callId")
                extras = _parse_extra_headers(
                    data.get("extra_headers") or start.get("extraHeaders")
                )
                session_id = extras.get("sessionId")
                tenant_id = extras.get("tenantId")

                session = sessions.get(session_id) if session_id else None
                if session is None and call_id:
                    session = sessions.get_by_call_id(call_id)
                if session is None:
                    logger.error(
                        "stream_start_unknown_session",
                        extras=extras,
                        call_id=call_id,
                    )
                    await websocket.close(code=1008)
                    return

                session_id = session.session_id
                tenant = await tenant_repo.get(tenant_id or session.tenant_id)
                if tenant is None or not tenant.enabled:
                    await orchestrator.fail_politely_and_end(
                        session.session_id, "Tenant not available"
                    )
                    await websocket.close(code=1008)
                    return

                try:
                    await orchestrator.start_stream(
                        websocket=websocket,
                        session=session,
                        tenant=tenant,
                        stream_id=stream_id or "",
                        call_id=call_id,
                    )
                except Exception as exc:
                    ERRORS.labels(component="stream").inc()
                    logger.exception("stream_start_failed", session_id=session_id)
                    # Politely inform via Speak is not available on open stream;
                    # end session and close.
                    await orchestrator.fail_politely_and_end(session.session_id, str(exc))
                    await websocket.close(code=1011)
                    return

            elif event == "media":
                if not session_id:
                    continue
                media = data.get("media") or {}
                payload = media.get("payload")
                if payload:
                    await orchestrator.on_media(session_id, payload)

            elif event == "dtmf":
                logger.info("dtmf_received", session_id=session_id, data=data)

            elif event in {"stop", "clearedAudio"}:
                logger.info("stream_event", event=event, session_id=session_id)

    except WebSocketDisconnect:
        logger.info("plivo_ws_disconnected", session_id=session_id)
    except Exception:
        ERRORS.labels(component="stream").inc()
        logger.exception("plivo_ws_error", session_id=session_id)
        if session_id:
            await orchestrator.fail_politely_and_end(session_id, "WebSocket error")
    finally:
        if session_id:
            session = sessions.get(session_id)
            if session and session.status != SessionStatus.ENDED:
                await orchestrator.end_stream(
                    session_id, reason=CallEndReason.HANGUP
                )
