from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__
from app.api import admin_tenants, health, plivo_stream, plivo_webhooks
from app.core.config import get_settings
from app.core.logging import configure_logging, get_logger
from app.db.mongo import close_mongo, connect_mongo, get_db
from app.db.redis import close_redis, connect_redis, get_redis
from app.hms.client import HmsClient
from app.prompts.loader import prompt_loader
from app.providers.registry import ProviderRegistry
from app.repositories.call_logs import CallLogRepository
from app.services.call_orchestrator import CallOrchestrator
from app.services.outbound import PlivoOutboundService
from app.sessions.manager import SessionManager
from app.tenants.cache import TenantCache
from app.tenants.repository import TenantRepository
from app.tenants.resolver import TenantResolver
from app.tools.handlers.appointments import (
    BookAppointmentHandler,
    CancelAppointmentHandler,
)
from app.tools.handlers.hospital import (
    DepartmentListHandler,
    DoctorAvailabilityHandler,
    GenerateBillHandler,
    LabReportsHandler,
    SendWhatsappHandler,
)
from app.tools.handlers.patient import CreatePatientHandler, PatientSearchHandler
from app.tools.handlers.transfer import TransferCallHandler
from app.tools.router import ToolRouter

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    configure_logging(
        level=settings.log_level,
        json_logs=settings.is_production or settings.environment != "development",
    )
    app.state.shutting_down = False
    app.state.settings = settings

    await connect_mongo(settings)
    await connect_redis(settings)
    db = get_db()
    redis = get_redis()

    hms = HmsClient(settings)
    await hms.start()

    plivo = PlivoOutboundService(settings)
    await plivo.start()

    tenant_repo = TenantRepository(db)
    tenant_cache = TenantCache(redis, settings)
    tenant_resolver = TenantResolver(tenant_repo, tenant_cache)
    call_logs = CallLogRepository(db)
    sessions = SessionManager(call_logs)

    # Orchestrator created early so transfer handler can close over it
    orchestrator_box: dict[str, CallOrchestrator] = {}

    async def transfer_fn(session, tenant, destination, reason):
        return await orchestrator_box["orch"].transfer(
            session, tenant, destination, reason
        )

    tool_router = ToolRouter(
        [
            PatientSearchHandler(hms),
            CreatePatientHandler(hms),
            BookAppointmentHandler(hms),
            CancelAppointmentHandler(hms),
            DoctorAvailabilityHandler(hms),
            DepartmentListHandler(hms, redis, settings),
            LabReportsHandler(hms),
            GenerateBillHandler(hms),
            SendWhatsappHandler(hms, settings),
            TransferCallHandler(transfer_fn),
        ]
    )
    providers = ProviderRegistry(settings, tool_router, prompt_loader)
    orchestrator = CallOrchestrator(
        settings=settings,
        sessions=sessions,
        providers=providers,
        plivo=plivo,
    )
    orchestrator_box["orch"] = orchestrator

    app.state.hms = hms
    app.state.plivo_service = plivo
    app.state.tenant_repo = tenant_repo
    app.state.tenant_cache = tenant_cache
    app.state.tenant_resolver = tenant_resolver
    app.state.session_manager = sessions
    app.state.orchestrator = orchestrator
    app.state.tool_router = tool_router

    logger.info("app_started", version=__version__, environment=settings.environment)
    try:
        yield
    finally:
        app.state.shutting_down = True
        logger.info("app_shutting_down")
        grace = settings.shutdown_grace_seconds
        try:
            await asyncio.wait_for(sessions.drain(), timeout=grace)
        except asyncio.TimeoutError:
            logger.warning("shutdown_drain_timeout", grace_seconds=grace)
        await hms.stop()
        await plivo.stop()
        await close_redis()
        await close_mongo()
        logger.info("app_stopped")


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="Healeka AI Voice Agent",
        version=__version__,
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"] if not settings.is_production else [],
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(health.router)
    app.include_router(admin_tenants.router)
    app.include_router(plivo_webhooks.router)
    app.include_router(plivo_stream.router)
    return app


app = create_app()
