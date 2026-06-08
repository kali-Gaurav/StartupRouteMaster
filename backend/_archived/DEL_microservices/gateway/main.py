
import os
import time
import asyncio
import logging
import uuid
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, Request, HTTPException, Depends, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx

# Shared imports
import sys
from pathlib import Path
shared_path = str(Path(__file__).resolve().parent.parent)
if shared_path not in sys.path:
    sys.path.append(shared_path)

from shared.config import Config
from shared.logging import setup_logging, request_id_var

# Initialize logging
setup_logging("gateway")
logger = logging.getLogger("gateway")

app = FastAPI(
    title="RouteMaster Gateway",
    description="FAANG-level Intelligent API Gateway",
    version="1.0.0"
)

# Middleware: Request ID & Logging
@app.middleware("http")
async def add_request_id(request: Request, call_next):
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4()))
    token = request_id_var.set(request_id)
    start_time = time.perf_counter()
    
    try:
        response = await call_next(request)
        process_time = (time.perf_counter() - start_time) * 1000
        response.headers["X-Process-Time"] = f"{process_time:.2f}ms"
        response.headers["X-Request-ID"] = request_id
        
        logger.info(
            f"Method: {request.method} Path: {request.url.path} "
            f"Status: {response.status_code} Duration: {process_time:.2f}ms"
        )
        return response
    finally:
        request_id_var.reset(token)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=Config.CORS_ALLOWED_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# HTTP Client for Proxying
client = httpx.AsyncClient(timeout=30.0)

@app.on_event("shutdown")
async def shutdown_event():
    await client.aclose()

# --- HEALTH CHECK ---
@app.get("/health")
async def health_check():
    return {"status": "online", "service": "gateway", "timestamp": time.time()}

# --- DYNAMIC PROXY ---
# In a real FAANG system, this would be more sophisticated (Service Discovery)
async def proxy_request(service_url: str, path: str, request: Request):
    url = f"{service_url}/{path}"
    body = await request.body()
    
    headers = dict(request.headers)
    headers["X-Request-ID"] = request_id_var.get() or str(uuid.uuid4())
    # Remove host header to avoid conflicts
    headers.pop("host", None)
    
    try:
        response = await client.request(
            method=request.method,
            url=url,
            params=request.query_params,
            headers=headers,
            content=body
        )
        return JSONResponse(
            status_code=response.status_code,
            content=response.json() if response.headers.get("content-type") == "application/json" else response.text
        )
    except httpx.HTTPError as exc:
        logger.error(f"Error proxying to {url}: {exc}")
        raise HTTPException(status_code=502, detail="Upstream service error")

# --- ROUTES ---

@app.api_route("/api/v1/auth/{path:path}", methods=["GET", "POST", "PUT", "DELETE"])
async def auth_proxy(request: Request, path: str):
    """Proxy all auth requests to the Auth Service."""
    return await proxy_request(Config.AUTH_SERVICE_URL, f"api/v1/auth/{path}", request)

@app.get("/api/v2/search/unified")
@app.post("/api/v2/search/unified")
async def search_proxy(request: Request):
    # Route to Search Service
    return await proxy_request(Config.SEARCH_SERVICE_URL, "api/v2/search/unified", request)

@app.get("/api/v2/live/{path:path}")
async def live_proxy(request: Request, path: str):
    return await proxy_request(Config.ROUTE_SERVICE_URL, f"api/v2/live/{path}", request)

@app.get("/")
async def root():
    return {"message": "RouteMaster Gateway V1.0 - Distributed System Entry"}
