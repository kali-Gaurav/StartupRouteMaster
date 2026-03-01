#!/bin/bash
# Start script for backend
echo "🚀 Starting app from backend folder..."
uvicorn app:app --host 0.0.0.0 --port $PORT --proxy-headers
