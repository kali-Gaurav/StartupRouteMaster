import logging
import sys
from pathlib import Path

from fastapi import FastAPI

logger = logging.getLogger("routemaster.routing")


def _safe_include(app: FastAPI, module_path: str, router_attr: str, prefix: str = "", label: str = "", **kwargs):
    """Safely import and register a router — logs a warning on failure instead of crashing."""
    try:
        import importlib
        mod = importlib.import_module(module_path)
        router = getattr(mod, router_attr)
        if prefix:
            app.include_router(router, prefix=prefix, **kwargs)
        else:
            app.include_router(router, **kwargs)
        logger.debug("Router registered: %s", label or module_path)
    except Exception as exc:
        logger.warning("Router skipped [%s]: %s", label or module_path, exc)


def register_routers(app: FastAPI):
    """
    Modularized Router Registry.
    Registers all API routes with per-group fault isolation.
    A single failing router module does NOT block the others.
    CRITICAL routes (search, stations, health) are registered first.
    """
    V1_PREFIX = "/api"
    V2_PREFIX = "/api/v2"
    V3_PREFIX = "/api/v3"

    # ─── PROMETHEUS (optional) ────────────────────────────────────────────────
    try:
        from prometheus_fastapi_instrumentator import Instrumentator
        from database.config import Config
        instrumentator = Instrumentator(
            should_group_status_codes=True,
            should_ignore_untemplated=True,
            should_respect_env_var=True,
            excluded_handlers=["/metrics", "/api/health", "/ping", "/docs", "/openapi.json"]
        )
        if not getattr(Config, "SLIM_MODE", True):
            instrumentator.instrument(app).expose(app, endpoint="/api/v2/monitoring/metrics")
        else:
            logger.info("Metrics: Slim Mode Active. Skipping Prometheus instrumentation.")
    except Exception as exc:
        logger.warning("Prometheus skipped: %s", exc)

    # ─── CRITICAL: SEARCH & STATIONS (must succeed) ───────────────────────────
    try:
        from api.search import search, stations
        app.include_router(search.router, prefix=V1_PREFIX)
        app.include_router(stations.router, prefix=V1_PREFIX)
        logger.info("Core search & station routes registered.")
    except Exception as exc:
        logger.error("CRITICAL: Search/station routes failed to register: %s", exc)

    # ─── CRITICAL: AUTH ───────────────────────────────────────────────────────
    try:
        from api.auth import auth, users
        app.include_router(auth.router, prefix=V1_PREFIX)
        app.include_router(users.router, prefix=V1_PREFIX)
        logger.info("Auth routes registered.")
    except Exception as exc:
        logger.warning("Auth routes skipped: %s", exc)

    # ─── CORE: BOOKINGS ───────────────────────────────────────────────────────
    try:
        from api.bookings import bookings, flow, integrated_search, booking_routes
        app.include_router(bookings.router, prefix=V1_PREFIX)
        app.include_router(stations.router, prefix=V1_PREFIX)
        app.include_router(flow.router, prefix=V1_PREFIX)
        app.include_router(integrated_search.router, prefix=V1_PREFIX)
        app.include_router(booking_routes.router)
        logger.info("Booking routes registered.")
    except Exception as exc:
        logger.warning("Booking routes skipped: %s", exc)

    # ─── CORE: SAFETY / SOS ───────────────────────────────────────────────────
    try:
        from api.safety import sos, vault, sathi
        app.include_router(sos.router, prefix=V1_PREFIX)
        app.include_router(vault.router, prefix=V1_PREFIX)
        app.include_router(sathi.router, prefix=V1_PREFIX)
        logger.info("Safety/SOS routes registered.")
    except Exception as exc:
        logger.warning("Safety routes skipped: %s", exc)

    # ─── CORE: PAYMENTS ───────────────────────────────────────────────────────
    try:
        from api.payments import payments, bank_webhooks, razorpay_standard, payment_webhook
        app.include_router(payments.router, prefix=V1_PREFIX)
        app.include_router(payments.router, prefix="/payments", include_in_schema=False)
        app.include_router(razorpay_standard.router, prefix=V1_PREFIX)
        app.include_router(bank_webhooks.router, prefix=V1_PREFIX)
        app.include_router(payment_webhook.router)
        logger.info("Payment routes registered.")
    except Exception as exc:
        logger.warning("Payment routes skipped: %s", exc)

    # ─── SYSTEM: STATUS, ADMIN ────────────────────────────────────────────────
    try:
        from api.system import status, tatkal
        app.include_router(status.router, prefix=V1_PREFIX)
        app.include_router(tatkal.router, prefix=V1_PREFIX)
    except Exception as exc:
        logger.warning("System routes skipped: %s", exc)

    try:
        from api.admin import admin as admin_v1, refunds as admin_refunds, reconciliation as admin_reconciliation
        app.include_router(admin_v1.router, prefix="/api/v1")
        app.include_router(admin_refunds.router, prefix=V1_PREFIX)
        app.include_router(admin_reconciliation.router, prefix=V1_PREFIX)
    except Exception as exc:
        logger.warning("Admin routes skipped: %s", exc)

    # ─── COMMUNICATION: CHAT, TELEGRAM ────────────────────────────────────────
    try:
        from api.communication import chat, chat_ws, telegram_bot
        app.include_router(chat.router, prefix=V1_PREFIX)
        app.include_router(chat_ws.router, prefix=V1_PREFIX)
        app.include_router(telegram_bot.router, prefix=V1_PREFIX)
    except Exception as exc:
        logger.warning("Communication routes skipped: %s", exc)

    # ─── V2 ROUTES (optional, each isolated) ─────────────────────────────────
    _v2_routers = [
        ("api.v2.search", "router", "search_v2"),
        ("api.v2.live", "router", "live"),
        ("api.v2.monitoring", "router", "monitoring"),
        ("api.v2.user", "router", "user_v2"),
        ("api.v2.booking", "router", "booking_v2"),
        ("api.v2.booking_ws", "router", "booking_ws"),
        ("api.v2.debug", "router", "debug"),
        ("api.v2.admin", "router", "admin_v2"),
        ("api.v2.admin_auth", "router", "admin_auth"),
        ("api.v2.agent", "router", "agent"),
        ("api.v2.agents", "router", "agents"),
        ("api.v2.unlock", "router", "unlock"),
        ("api.v2.webhooks", "router", "webhooks"),
        ("api.v2.sessions", "router", "sessions"),
        ("api.v2.external_api", "router", "external_api"),
        ("api.v2.notifications", "router", "notifications"),
        ("api.v2.realtime", "router", "realtime"),
        ("api.v2.credits", "router", "credits_v2"),
        ("api.v2.karma", "router", "karma"),
        ("api.v2.admin_commissions", "router", "admin_commissions"),
        ("api.v2.admin_fraud", "router", "admin_fraud"),
        ("api.v2.ledger", "router", "ledger_v2"),
        ("api.v2.trips", "router", "trips_v2"),
        ("api.v2.sathi", "router", "sathi_v2"),
    ]
    for mod_path, attr, label in _v2_routers:
        _safe_include(app, mod_path, attr, prefix=V2_PREFIX, label=label)

    # ─── V3 ROUTES (optional, each isolated) ─────────────────────────────────
    _v3_routers = [
        ("api.v3.search", "router", "search_v3"),
        ("api.v3.transit", "router", "transit_v3"),
        ("api.v3.governor", "router", "governor_v3"),
        ("api.v3.system", "router", "system_v3"),
        ("api.v3.model_search", "router", "model_search_v3"),
        ("api.v3.sos", "router", "sos_v3"),
        ("api.v3.bookings", "router", "bookings_v3"),
        ("api.v3.guardian", "router", "guardian_v3"),
        ("api.v3.intelligence", "router", "intelligence_v3"),
    ]
    for mod_path, attr, label in _v3_routers:
        _safe_include(app, mod_path, attr, prefix=V3_PREFIX, label=label)

    # ─── INTELLIGENCE & EVOLUTION (optional) ─────────────────────────────────
    _intel_routers = [
        ("api.intelligence.knowledge_api", "router", "knowledge_api"),
        ("api.intelligence.execution", "router", "execution"),
        ("api.intelligence.redistribution", "router", "redistribution"),
        ("api.intelligence.revenue", "router", "revenue"),
        ("api.routes.cat_api", "router", "cat_api"),
        ("api.routes.route_engine_api", "api_router", "route_engine_api"),
        ("api.routes.synthetic_data_api", "router", "synthetic_data_api"),
    ]
    for mod_path, attr, label in _intel_routers:
        _safe_include(app, mod_path, attr, label=label)

    # ─── VOICE & ANALYTICS (optional) ────────────────────────────────────────
    _safe_include(app, "api.safety.voice_v1", "router", prefix="/api", label="voice_v1")
    _safe_include(app, "api.system.analytics_v1", "router", prefix="/api", label="analytics_v1")

    # ─── TRAVEL PLANNING (optional) ───────────────────────────────────────────
    _safe_include(app, "services.planning.api", "router", prefix="/api", label="travel_planning")

    logger.info("Router registration complete.")
