#!/bin/bash
# RouteMaster V2: Self-Healing Backend Orchestrator
# Task 20.2: Automatic Restart Loop & Database Migration

echo "🛡️ RouteMaster Bootstrap: Initializing..."

# Ensure the script runs from the backend directory regardless of the caller's cwd
cd "$(dirname "$0")"

# 1. Run database migrations to ensure schema is production-ready
echo "📦 Running Database Migrations (Alembic)..."
alembic upgrade head
MIGRATION_STATUS=$?
if [ $MIGRATION_STATUS -ne 0 ]; then
    echo "❌ CRITICAL: Database migration failed. Exiting deployment."
    exit 1
fi
echo "✅ Migrations complete."

echo "🛡️ RouteMaster Watchdog: Entering process loop..."
while true; do
    echo "🚀 Starting app protocol v2.5..."
    
    if [ -f "backup_system.py" ]; then
        python backup_system.py || echo "⚠️ Backup system non-fatal failure."
    fi
    
    if [ "$ENVIRONMENT" = "production" ]; then
        # Run Gunicorn with Uvicorn workers (Production Mode)
        if [ -f "gunicorn_conf.py" ]; then
            gunicorn -c gunicorn_conf.py app:app
        else
            gunicorn -k uvicorn.workers.UvicornWorker --bind 0.0.0.0:8000 --workers 4 --timeout 120 app:app
        fi
    else
        # Development / Fallback
        python -m uvicorn app:app --host 0.0.0.0 --port 8000 --workers 1
    fi
    
    EXIT_CODE=$?
    echo "⚠️ Backend process exited with code $EXIT_CODE"
    
    if [ $EXIT_CODE -eq 0 ]; then
        echo "🛑 Clean shutdown detected. Exiting watchdog."
        exit 0
    fi
    
    echo "🔄 Critical failure detected. Restarting in 5 seconds..."
    sleep 5
done
