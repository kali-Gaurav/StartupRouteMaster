import logging
import sys
from pathlib import Path

from fastapi import FastAPI

logger = logging.getLogger("routemaster.routing")

def register_routers(app: FastAPI):
    """
    Task 2: Modularized Router Registry. 
    Registers all V1 and V2 API routes safely and instruments with Prometheus.
    """

    # Task 40: Selective Prometheus Instrumentation
    from prometheus_fastapi_instrumentator import Instrumentator
    from database.config import Config
    
    instrumentator = Instrumentator(
        should_group_status_codes=True,
        should_ignore_untemplated=True,
        should_respect_env_var=True,
        excluded_handlers=["/metrics", "/api/health", "/ping", "/docs", "/openapi.json"]
    )
    
    if not Config.SLIM_MODE:
        instrumentator.instrument(app).expose(app, endpoint="/api/v2/monitoring/metrics")
    else:
        logger.info("Metrics: Slim Mode Active. Skipping full Prometheus instrumentation.")

    # --- V2 API ROUTES ---
    from api.v2 import (
        search as search_v2, live, monitoring, user as user_v2, 
        booking as booking_v2, booking_ws, debug, admin, 
        admin_auth, agent, agents, unlock, webhooks, sessions, external_api,
        notifications, realtime, credits as credits_v2, karma,
        admin_commissions, admin_fraud
    )
    V2_PREFIX = "/api/v2"
    app.include_router(search_v2.router, prefix=V2_PREFIX)
    app.include_router(live.router, prefix=V2_PREFIX)
    app.include_router(monitoring.router, prefix=V2_PREFIX)
    app.include_router(user_v2.router, prefix=V2_PREFIX)
    app.include_router(booking_v2.router, prefix=V2_PREFIX)
    app.include_router(booking_ws.router, prefix=V2_PREFIX)
    app.include_router(debug.router, prefix=V2_PREFIX)
    app.include_router(admin.router, prefix=V2_PREFIX)
    app.include_router(admin_auth.router, prefix=V2_PREFIX)
    app.include_router(agent.router, prefix=V2_PREFIX)
    app.include_router(agents.router, prefix=V2_PREFIX)
    app.include_router(unlock.router, prefix=V2_PREFIX)
    app.include_router(webhooks.router, prefix=V2_PREFIX)
    app.include_router(sessions.router, prefix=V2_PREFIX)
    app.include_router(external_api.router, prefix=V2_PREFIX)
    app.include_router(notifications.router, prefix=V2_PREFIX)
    app.include_router(realtime.router, prefix=V2_PREFIX)
    app.include_router(credits_v2.router, prefix=V2_PREFIX)
    app.include_router(karma.router, prefix=V2_PREFIX)
    app.include_router(admin_commissions.router, prefix=V2_PREFIX)
    app.include_router(admin_fraud.router, prefix=V2_PREFIX)

    # --- AGENT SWARM API ---
    from api.v2.agents import router as agents_router
    app.include_router(agents_router, prefix=V2_PREFIX)

    from api.v3 import (
        search as search_v3, transit as transit_v3, governor as governor_v3, 
        system as system_v3, model_search as model_search_v3, sos as sos_v3,
        bookings as bookings_v3, guardian as guardian_v3, intelligence as intelligence_v3
    )
    V3_PREFIX = "/api/v3"
    app.include_router(search_v3.router, prefix=V3_PREFIX)
    app.include_router(transit_v3.router, prefix=V3_PREFIX)
    app.include_router(governor_v3.router, prefix=V3_PREFIX)
    app.include_router(system_v3.router, prefix=V3_PREFIX)
    app.include_router(model_search_v3.router, prefix=V3_PREFIX)
    app.include_router(sos_v3.router, prefix=V3_PREFIX)
    app.include_router(bookings_v3.router, prefix=V3_PREFIX)
    app.include_router(guardian_v3.router, prefix=V3_PREFIX)
    app.include_router(intelligence_v3.router, prefix=V3_PREFIX)

    # --- V1 API ROUTES ---
    from api import (
        chat, chat_ws, sos, search, bookings, stations,
        payments, auth, users, flow, bank_webhooks,
        admin_refunds, admin_reconciliation, tatkal,
        telegram_bot, vault, status, admin as admin_v1,
        integrated_search
    )
    V1_PREFIX = "/api"
    app.include_router(status.router, prefix=V1_PREFIX)
    app.include_router(sos.router, prefix=V1_PREFIX)
    app.include_router(chat.router, prefix=V1_PREFIX)
    app.include_router(chat_ws.router, prefix=V1_PREFIX)
    app.include_router(search.router, prefix=V1_PREFIX)
    app.include_router(bookings.router, prefix=V1_PREFIX)
    app.include_router(stations.router, prefix=V1_PREFIX)
    app.include_router(payments.router, prefix=V1_PREFIX)
    app.include_router(auth.router, prefix=V1_PREFIX)
    app.include_router(users.router, prefix=V1_PREFIX)
    app.include_router(flow.router, prefix=V1_PREFIX)
    app.include_router(bank_webhooks.router, prefix=V1_PREFIX)
    app.include_router(admin_refunds.router, prefix=V1_PREFIX)
    app.include_router(admin_reconciliation.router, prefix=V1_PREFIX)
    app.include_router(tatkal.router, prefix=V1_PREFIX)
    app.include_router(telegram_bot.router, prefix=V1_PREFIX)
    app.include_router(vault.router, prefix=V1_PREFIX)
    app.include_router(integrated_search.router, prefix=V1_PREFIX)
    app.include_router(admin_v1.router, prefix="/api/v1")
    
    # [P16] High-Value Voice & Analytics Gateway Integration
    from api import voice_v1, analytics_v1
    app.include_router(voice_v1.router, prefix="/api")
    app.include_router(analytics_v1.router, prefix="/api")

    # --- PATENT INNOVATION: Travel Planning System ---
    # Crowd Control, Multi-Modal Planning, Station Amenities
    from services.travel_planning_api import router as travel_planning_router
    app.include_router(travel_planning_router, prefix="/api")
