from __future__ import annotations

from fastapi import APIRouter, Request, Response

from app.core.metrics import metrics_payload, snapshot
from app.db.mongo import mongo
from app.db.redis import redis_state

router = APIRouter(tags=["health"])


@router.get("/health")
async def health() -> dict:
    return {"status": "ok", **snapshot()}


@router.get("/live")
async def liveness() -> dict:
    return {"status": "alive"}


@router.get("/ready")
async def readiness(request: Request) -> Response:
    shutting_down = getattr(request.app.state, "shutting_down", False)
    mongo_ok = mongo.db is not None
    redis_ok = (not redis_state.enabled) or (redis_state.client is not None)
    if shutting_down or not mongo_ok or not redis_ok:
        return Response(
            content='{"status":"not_ready"}',
            status_code=503,
            media_type="application/json",
        )
    return Response(
        content='{"status":"ready"}',
        status_code=200,
        media_type="application/json",
    )


@router.get("/metrics")
async def metrics() -> Response:
    body, content_type = metrics_payload()
    return Response(content=body, media_type=content_type)
