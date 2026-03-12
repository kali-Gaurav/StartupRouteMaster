#!/bin/bash
# RouteMaster V2: Self-Healing Backend Orchestrator
# Task 20.2: Automatic Restart Loop

echo "🛡️ RouteMaster Watchdog: Initializing..."

while true; do
    echo "🚀 Starting app protocol v2.5..."
    python backup_system.py # Backup before each start
    
    # Run uvicorn
    uvicorn app:app --host 0.0.0.0 --port ${PORT:-8000} --proxy-headers
    
    EXIT_CODE=$?
    echo "⚠️ Backend process exited with code $EXIT_CODE"
    
    if [ $EXIT_CODE -eq 0 ]; then
        echo "🛑 Clean shutdown detected. Exiting watchdog."
        exit 0
    fi
    
    echo "🔄 Critical failure detected. Restarting in 5 seconds..."
    sleep 5
done
