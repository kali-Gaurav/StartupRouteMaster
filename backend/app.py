from __future__ import annotations

import importlib
import logging
import os
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import Any, Callable, Dict, List, Optional

# Ensure backend package root is importable when running from repo root
backend_root = Path(__file__).resolve().parent
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from config import BootstrapConfigError, BootstrapSettings, get_bootstrap_settings
from utils.structured_logging import setup_logging


def _configure_event_loop() -> None:
    try:
        import asyncio

        if sys.platform == "win32":
            asyncio.set_event_loop_policy(asyncio.WindowsProactorEventLoopPolicy())
            return

        import uvloop

        asyncio.set_event_loop_policy(uvloop.EventLoopPolicy())
    except ImportError:
        return
    except Exception:
        return


_configure_event_loop()
setup_logging()
logger = logging.getLogger("api-gateway")


class BootstrapIntegrationError(RuntimeError):
    """Raised when an optional bootstrap integration cannot be loaded."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _record_bootstrap_warning(app: FastAPI, warning: str) -> None:
    state = getattr(app.state, "bootstrap", None)
    if state is None:
        app.state.bootstrap = {"warnings": [warning], "components": {}}
        return
    warnings: List[str] = state.setdefault("warnings", [])
    if warning not in warnings:
        warnings.append(warning)


def _update_component_state(app: FastAPI, component: str, status: str, detail: Optional[str] = None) -> None:
    state = getattr(app.state, "bootstrap", None)
    if state is None:
        app.state.bootstrap = {"warnings": [], "components": {}}
        state = app.state.bootstrap

    payload: Dict[str, Any] = {"status": status}
    if detail:
        payload["detail"] = detail
    state.setdefault("components", {})[component] = payload


def _load_callable(module_name: str, attr_name: str) -> Callable[..., Any]:
    module = importlib.import_module(module_name)
    try:
        return getattr(module, attr_name)
    except AttributeError as exc:
        raise BootstrapIntegrationError(
            f"Missing attribute '{attr_name}' in module '{module_name}'."
        ) from exc


@asynccontextmanager
async def _noop_lifespan(_: FastAPI):
    yield


def _resolve_lifespan(settings: BootstrapSettings) -> Callable[..., Any]:
    if settings.use_simple_lifespan:
        return _load_callable("core.lifespan_simple", "lifespan")

    try:
        return _load_callable("core.lifespan", "lifespan")
    except Exception as exc:
        if not settings.allow_degraded_boot:
            raise BootstrapIntegrationError("Failed to load production lifespan.") from exc
        logger.exception("Production lifespan unavailable; falling back to simplified lifespan.")
        return _load_callable("core.lifespan_simple", "lifespan")


def _setup_exception_handlers(app: FastAPI, settings: BootstrapSettings) -> None:
    try:
        setup_exception_handlers = _load_callable("core.exceptions", "setup_exception_handlers")
        setup_exception_handlers(app)
        _update_component_state(app, "exception_handlers", "loaded")
    except Exception as exc:
        if not settings.allow_degraded_boot:
            raise
        logger.exception("Exception handler bootstrap failed.")
        _record_bootstrap_warning(app, f"exception_handlers_unavailable: {exc}")
        _update_component_state(app, "exception_handlers", "degraded", str(exc))


def _setup_middleware(app: FastAPI, settings: BootstrapSettings) -> None:
    try:
        middleware_module = importlib.import_module("core.middleware")
        setup_middleware = getattr(middleware_module, "setup_middleware", None)
        if setup_middleware is None:
            raise BootstrapIntegrationError("core.middleware.setup_middleware is not available.")
        setup_middleware(app)
        _update_component_state(app, "middleware", "loaded")
    except Exception as exc:
        if not settings.allow_degraded_boot:
            raise
        logger.exception("Middleware bootstrap failed.")
        _record_bootstrap_warning(app, f"middleware_unavailable: {exc}")
        _update_component_state(app, "middleware", "degraded", str(exc))


def _register_routers(app: FastAPI, settings: BootstrapSettings) -> None:
    if not settings.register_api_routes:
        _update_component_state(app, "routers", "disabled", "REGISTER_API_ROUTES=false")
        return

    try:
        register_routers = _load_callable("core.routing", "register_routers")
        register_routers(app)
        _update_component_state(app, "routers", "loaded")
    except Exception as exc:
        if not settings.allow_degraded_boot:
            raise
        logger.exception("Router registration failed; application will run in degraded bootstrap mode.")
        _record_bootstrap_warning(app, f"router_registration_failed: {exc}")
        _update_component_state(app, "routers", "degraded", str(exc))
    
    # Register Telegram webhook routes
    try:
        from telegram_bot.integration import register_with_app
        register_with_app(app)
        _update_component_state(app, "telegram_webhook", "loaded")
        logger.info("Telegram webhook routes registered")
    except Exception as exc:
        logger.warning(f"Telegram webhook registration failed: {exc}")
        _record_bootstrap_warning(app, f"telegram_webhook_unavailable: {exc}")
        _update_component_state(app, "telegram_webhook", "degraded", str(exc))


def _mount_static_files(app: FastAPI, settings: BootstrapSettings) -> None:
    settings.media_sos_root.mkdir(parents=True, exist_ok=True)
    app.mount("/media", StaticFiles(directory=str(settings.media_root)), name="media")
    _update_component_state(app, "static_files", "loaded")


def _build_health_payload(app: FastAPI) -> Dict[str, Any]:
    bootstrap = getattr(app.state, "bootstrap", {"warnings": [], "components": {}})
    runtime_components = getattr(app.state, "runtime_components", {})
    components: Dict[str, str] = {
        "database": runtime_components.get("database", "unknown"),
        "redis": runtime_components.get("redis", "unknown"),
        "route_engine": runtime_components.get("route_engine", "unknown"),
        "external_api": runtime_components.get("external_api", "unknown"),
        "routers": bootstrap.get("components", {}).get("routers", {}).get("status", "unknown"),
        "middleware": bootstrap.get("components", {}).get("middleware", {}).get("status", "unknown"),
    }

    try:
        nexus_boot = getattr(importlib.import_module("core.nexus.bootstrapper"), "nexus_boot")
        system_state = getattr(importlib.import_module("core.nexus.state"), "SystemState")
        state_value = getattr(nexus_boot.state, "value", str(nexus_boot.state))
        components["nexus"] = state_value
        if nexus_boot.state == system_state.READY:
            components["route_engine"] = "loaded"
            components["database"] = "ready"
    except Exception as exc:
        components["nexus"] = "unavailable"
        _record_bootstrap_warning(app, f"nexus_state_unavailable: {exc}")

    essential_components = {
        "routers": components["routers"],
        "database": components["database"],
        "route_engine": components["route_engine"],
    }
    healthy = all(status in {"ready", "loaded", "up"} for status in essential_components.values())
    status = "healthy" if healthy else "degraded"
    readiness = "ready" if healthy else "degraded"

    return {
        "status": status,
        "readiness": readiness,
        "timestamp": _utc_now(),
        "environment": getattr(app.state, "settings").environment,
        "bootstrap_mode": "degraded" if bootstrap.get("warnings") else "normal",
        "warnings": bootstrap.get("warnings", []),
        "components": components,
        "database": "up" if components["database"] in {"ready", "up"} else components["database"],
        "route_engine": components["route_engine"],
    }


def create_app(settings: Optional[BootstrapSettings] = None) -> FastAPI:
    settings = settings or get_bootstrap_settings()
    settings.validate()

    app = FastAPI(
        title="RouteMaster V3",
        description="Industrial-grade railway search platform bootstrap gateway.",
        version="3.0.0",
        lifespan=_resolve_lifespan(settings),
    )
    app.state.settings = settings
    app.state.bootstrap = {"warnings": [], "components": {}}

    _setup_exception_handlers(app, settings)
    _setup_middleware(app, settings)
    _register_routers(app, settings)
    _mount_static_files(app, settings)
    _register_bootstrap_routes(app)
    return app


def _register_bootstrap_routes(app: FastAPI) -> None:
    @app.get("/", tags=["Health"])
    async def root() -> Dict[str, Any]:
        return {
            "message": "RouteMaster bootstrap online.",
            "timestamp": _utc_now(),
            "bootstrap_mode": _build_health_payload(app)["bootstrap_mode"],
        }

    @app.get("/ping", tags=["Health"])
    async def ping() -> Dict[str, str]:
        return {"status": "pong", "timestamp": _utc_now()}

    @app.post("/chat", tags=["Compatibility"])
    async def chat_alias():
        return RedirectResponse(url="/api/chat", status_code=307)

    @app.get("/health", tags=["Health"])
    @app.get("/api/health", tags=["Health"])
    async def api_health() -> Dict[str, Any]:
        return _build_health_payload(app)

    @app.get("/health/live", tags=["Health"])
    @app.get("/api/health/live", tags=["Health"])
    async def api_health_live() -> Dict[str, str]:
        return {"status": "alive", "timestamp": _utc_now()}

    @app.get("/health/ready", tags=["Health"])
    @app.get("/api/health/ready", tags=["Health"])
    async def api_health_ready() -> Dict[str, Any]:
        payload = _build_health_payload(app)
        return {
            "status": payload["readiness"],
            "timestamp": payload["timestamp"],
            "database": payload["components"]["database"],
            "route_engine": payload["components"]["route_engine"],
            "components": {
                "database": payload["components"]["database"],
                "route_engine": payload["components"]["route_engine"],
                "routers": payload["components"]["routers"],
            },
            "warnings": payload["warnings"],
        }

    @app.get("/stats", tags=["Health"])
    @app.get("/api/stats", tags=["Health"])
    async def api_stats() -> Dict[str, Any]:
        try:
            nexus_governor = getattr(importlib.import_module("core.nexus.audit.governor"), "nexus_governor")
            nexus_telemetry = getattr(importlib.import_module("core.nexus.telemetry"), "nexus_telemetry")
            gov_stats = await nexus_governor.get_stats()
            telemetry_metrics = await nexus_telemetry.get_metrics()
            return {
                "cpu": gov_stats.get("cpu_percent", 0),
                "ram": gov_stats.get("ram_percent", 0),
                "latency_ms": telemetry_metrics.get("avg_latency_ms", 0),
                "requests_per_sec": telemetry_metrics.get("requests_per_sec", 0),
                "timestamp": _utc_now(),
            }
        except Exception as exc:
            logger.exception("Stats endpoint degraded.")
            return {
                "cpu": 0,
                "ram": 0,
                "latency_ms": 0,
                "requests_per_sec": 0,
                "timestamp": _utc_now(),
                "warning": str(exc),
            }


try:
    app = create_app()
except BootstrapConfigError:
    raise
except Exception as exc:
    logger.exception("Fatal bootstrap error while creating application.")
    raise BootstrapIntegrationError("Application bootstrap failed.") from exc


if __name__ == "__main__":
    import uvicorn

    bootstrap_settings = get_bootstrap_settings()
    uvicorn.run(
        "app:app",
        host=bootstrap_settings.host,
        port=bootstrap_settings.port,
        reload=False,
    )
