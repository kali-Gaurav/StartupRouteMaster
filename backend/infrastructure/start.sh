#!/bin/bash
# RouteMaster V2: Backend Startup Script

echo "🚀 Starting RouteMaster Backend..."
cd "$(dirname "$0")/.."

if [ "$ENVIRONMENT" = "production" ]; then
    # Run Gunicorn with Uvicorn workers (Production Mode)
    if [ -f "infrastructure/gunicorn_conf.py" ]; then
        exec gunicorn -c infrastructure/gunicorn_conf.py app:app
    else
        WORKERS=${WEB_CONCURRENCY:-2}
        exec gunicorn -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --workers $WORKERS --timeout 120 --forwarded-allow-ips="*" app:app
    fi
else
    # Development / Fallback
    exec python -m uvicorn app:app --host 0.0.0.0 --port 8000 --workers 1 --proxy-headers
fi
