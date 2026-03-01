#!/bin/bash
# Start script for Railway / Railpack
echo "🚀 Starting backend service..."
cd backend && uvicorn app:app --host 0.0.0.0 --port $PORT --proxy-headers
