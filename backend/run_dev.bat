@echo off
TITLE RouteMaster V2: Self-Healing Watchdog
echo 🛡️ RouteMaster Watchdog (Windows): Initializing...

:start
echo 🚀 Starting app protocol v2.5...
python backup_system.py

:: Run uvicorn
uvicorn app:app --host 0.0.0.0 --port 8000 --reload

echo ⚠️ Backend process exited with code %errorlevel%

if %errorlevel% equ 0 (
    echo 🛑 Clean shutdown detected.
    pause
    exit /b 0
)

echo 🔄 Critical failure detected. Restarting in 5 seconds...
timeout /t 5
goto start
