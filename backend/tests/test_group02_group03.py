from __future__ import annotations

import pathlib
import tomllib

from backend import gunicorn_conf

ROOT = pathlib.Path(__file__).resolve().parent.parent
BACKEND = ROOT


def test_gunicorn_conf_values():
    assert gunicorn_conf.bind == "0.0.0.0:8000"
    assert gunicorn_conf.workers == 2
    assert gunicorn_conf.timeout == 60
    assert gunicorn_conf.max_requests == 550
    assert gunicorn_conf.max_requests_jitter == 50
    assert gunicorn_conf.forwarded_allow_ips == "*"
    assert gunicorn_conf.proxy_allow_ips == "*"


def test_run_dev_script_is_dev_safe():
    run_dev_path = BACKEND / "run_dev.py"
    content = run_dev_path.read_text()
    assert "uvicorn.run(" in content
    assert "\"app:app\"" in content
    assert "reload=True" in content
    assert "ENVIRONMENT" in content


def test_windows_run_dev_batch_uses_python_module():
    content = (BACKEND / "run_dev.bat").read_text().lower()
    assert "python -m uvicorn app:app --host 0.0.0.0 --port 8000 --reload" in content
    assert "timeout /t 5" in content
    assert "goto start" in content


def test_start_sh_bootstrap_behavior():
    content = (BACKEND / "start.sh").read_text()
    assert "cd \"$(dirname \"$0\")\"" in content
    assert "alembic upgrade head" in content
    assert "gunicorn -c gunicorn_conf.py app:app" in content
    assert "python -m uvicorn app:app --host 0.0.0.0 --port 8000 --workers 1" in content


def test_procfile_uses_uvicorn_web_command():
    content = (BACKEND / "Procfile").read_text().strip()
    assert content == "web: uvicorn app:app --host 0.0.0.0 --port $PORT --proxy-headers"


def test_dependency_pins_are_consistent():
    pyproject_text = (BACKEND / "pyproject.toml").read_text(encoding="utf-8")
    with (BACKEND / "pyproject.toml").open("rb") as f:
        pyproject_data = tomllib.load(f)

    project_deps = pyproject_data["project"]["dependencies"]
    requirements = (BACKEND / "requirements.txt").read_text().splitlines()
    req_map = {}
    for line in requirements:
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        if "==" in line:
            name, version = line.split("==", 1)
            req_map[name.strip()] = version.strip()

    assert req_map["tenacity"] == "8.2.3"
    assert req_map["httpx"] == "0.25.2"
    assert any(dep.startswith("tenacity==8.2.3") for dep in project_deps)
    assert any(dep.startswith("httpx==0.25.2") for dep in project_deps)


def test_runtime_and_railpack_are_present():
    runtime = (BACKEND / "runtime.txt").read_text().strip()
    assert runtime.startswith("python-3.11")
    railpack = (BACKEND / "railpack.json").read_text().strip()
    assert "uvicorn app:app --host 0.0.0.0 --port $PORT --proxy-headers" in railpack
