from __future__ import annotations

import types

import pytest
from fastapi import HTTPException
from fastapi.testclient import TestClient

import app as app_module
import background_worker as worker_module
from config import BootstrapConfigError, BootstrapSettings


def make_settings(**overrides) -> BootstrapSettings:
    base = {
        "environment": "test",
        "host": "127.0.0.1",
        "port": 8000,
        "log_level": "INFO",
        "media_root": app_module.get_bootstrap_settings().media_root,
        "media_sos_root": app_module.get_bootstrap_settings().media_sos_root,
        "use_simple_lifespan": False,
        "allow_degraded_boot": True,
        "register_api_routes": True,
        "enable_worker_swarm": False,
        "enable_worker_watchdog": False,
        "heartbeat_log_path": app_module.get_bootstrap_settings().heartbeat_log_path,
        "route_engine_init_timeout_sec": 0.1,
    }
    base.update(overrides)
    return BootstrapSettings(**base)


def test_bootstrap_settings_reject_invalid_port():
    with pytest.raises(BootstrapConfigError):
        make_settings(port=70000).validate()


def test_create_app_bootstraps_health_routes_in_isolation(monkeypatch):
    monkeypatch.setattr(app_module, "_resolve_lifespan", lambda settings: app_module._noop_lifespan)
    ready_state = object()

    class FakeState:
        value = "READY"

        def __eq__(self, other):
            return other is ready_state

    def fake_setup_exceptions(app, settings):
        app_module._update_component_state(app, "exception_handlers", "loaded")

    def fake_setup_middleware(app, settings):
        app_module._update_component_state(app, "middleware", "loaded")

    def fake_register_routers(app, settings):
        app_module._update_component_state(app, "routers", "loaded")

    real_import = app_module.importlib.import_module

    def fake_import(name: str):
        if name == "core.nexus.bootstrapper":
            return types.SimpleNamespace(nexus_boot=types.SimpleNamespace(state=FakeState()))
        if name == "core.nexus.state":
            return types.SimpleNamespace(SystemState=types.SimpleNamespace(READY=ready_state))
        return real_import(name)

    monkeypatch.setattr(app_module, "_setup_exception_handlers", fake_setup_exceptions)
    monkeypatch.setattr(app_module, "_setup_middleware", fake_setup_middleware)
    monkeypatch.setattr(app_module, "_register_routers", fake_register_routers)
    monkeypatch.setattr(app_module.importlib, "import_module", fake_import)

    application = app_module.create_app(make_settings())
    client = TestClient(application)

    health = client.get("/api/health")
    ready = client.get("/api/health/ready")

    assert health.status_code == 200
    payload = health.json()
    assert payload["status"] == "healthy"
    assert payload["components"]["routers"] == "loaded"
    assert payload["components"]["middleware"] == "loaded"

    assert ready.status_code == 200
    ready_payload = ready.json()
    assert ready_payload["status"] == "ready"
    assert ready_payload["components"]["routers"] == "loaded"


def test_create_app_reports_degraded_router_registration(monkeypatch):
    monkeypatch.setattr(app_module, "_resolve_lifespan", lambda settings: app_module._noop_lifespan)
    monkeypatch.setattr(
        app_module,
        "_setup_exception_handlers",
        lambda app, settings: app_module._update_component_state(app, "exception_handlers", "loaded"),
    )
    monkeypatch.setattr(
        app_module,
        "_setup_middleware",
        lambda app, settings: app_module._update_component_state(app, "middleware", "loaded"),
    )

    def fake_register_failure(app, settings):
        app_module._record_bootstrap_warning(app, "router_registration_failed: broken import")
        app_module._update_component_state(app, "routers", "degraded", "broken import")

    monkeypatch.setattr(app_module, "_register_routers", fake_register_failure)

    application = app_module.create_app(make_settings())
    client = TestClient(application)

    health = client.get("/api/health")
    ready = client.get("/api/health/ready")

    assert health.status_code == 200
    assert health.json()["bootstrap_mode"] == "degraded"
    assert health.json()["components"]["routers"] == "degraded"

    assert ready.status_code == 200
    assert ready.json()["status"] == "degraded"


@pytest.mark.asyncio
async def test_background_worker_agent_swarm_disabled(monkeypatch):
    stop_event = worker_module.asyncio.Event()
    stop_event.set()
    monkeypatch.setattr(
        worker_module,
        "get_bootstrap_settings",
        lambda: make_settings(enable_worker_swarm=False),
    )

    await worker_module.run_agent_swarm(stop_event)


@pytest.mark.asyncio
async def test_background_worker_watchdog_disabled(monkeypatch):
    stop_event = worker_module.asyncio.Event()
    stop_event.set()
    monkeypatch.setattr(
        worker_module,
        "get_bootstrap_settings",
        lambda: make_settings(enable_worker_watchdog=False),
    )

    await worker_module.run_watchdog_loop(stop_event)


def test_extract_bearer_token_rejects_missing_or_invalid_header():
    import dependencies as dependencies_module

    with pytest.raises(HTTPException) as exc_missing:
        dependencies_module._extract_bearer_token(None)
    assert exc_missing.value.status_code == 401

    with pytest.raises(HTTPException) as exc_scheme:
        dependencies_module._extract_bearer_token("Basic token")
    assert exc_scheme.value.status_code == 401


def test_decode_token_raises_when_secret_not_configured(monkeypatch):
    import dependencies as dependencies_module

    monkeypatch.setattr(dependencies_module.Config, "SUPABASE_JWT_SECRET", "")

    with pytest.raises(HTTPException) as exc:
        dependencies_module._decode_token("dummy-token")
    assert exc.value.status_code == 500


def test_bootstrap_settings_defaults_from_env(monkeypatch, tmp_path):
    monkeypatch.setenv("ENVIRONMENT", "development")
    monkeypatch.setenv("HOST", "127.0.0.1")
    monkeypatch.setenv("PORT", "12345")
    monkeypatch.setenv("LOG_LEVEL", "DEBUG")
    monkeypatch.setenv("MEDIA_ROOT", str(tmp_path / "media"))

    settings = BootstrapSettings.from_env()

    assert settings.environment == "development"
    assert settings.host == "127.0.0.1"
    assert settings.port == 12345
    assert settings.log_level == "DEBUG"
    assert settings.media_root == (tmp_path / "media").resolve()
    assert settings.register_api_routes is True
    assert settings.allow_degraded_boot is True
