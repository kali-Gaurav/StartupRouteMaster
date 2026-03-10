@echo off
REM Start the backend in development mode
set ENVIRONMENT=development
cd /d "%~dp0"

IF "%1"=="prod-parity" (
    echo 🚀 Running with GUNICORN (Production Parity Mode)
    .venv\Scripts\python.exe -m gunicorn -k uvicorn.workers.UvicornWorker --bind 127.0.0.1:8000 --workers 4 app:app
) ELSE (
    echo 🛠️ Running with UVICORN (Standard Dev Mode)
    .venv\Scripts\uvicorn.exe app:app --reload --host 127.0.0.1 --port 8000
)
