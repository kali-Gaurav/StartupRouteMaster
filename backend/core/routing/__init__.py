import logging
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
        logger.info("📊 Metrics: Slim Mode Active. Skipping full Prometheus instrumentation.")

    # --- V2 API ROUTES ---
    from api.v2 import (
        search as search_v2, live, monitoring, user as user_v2, 
        booking as booking_v2, booking_ws, debug, admin, 
        admin_auth, agent, unlock, webhooks, sessions, external_api,
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
