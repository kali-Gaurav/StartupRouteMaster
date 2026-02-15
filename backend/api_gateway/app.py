from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import httpx
import os
import time
from typing import Dict, Any, Optional
import logging

app = FastAPI(title="Railway Intelligence API Gateway", version="1.0.0")

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Service endpoints
SERVICES = {
    "scraper": os.getenv("SCRAPER_URL", "http://scraper:8001"),
    "route": os.getenv("ROUTE_URL", "http://route_service:8002"),
    "rl": os.getenv("RL_URL", "http://rl_service:8003"),
    "user": os.getenv("USER_URL", "http://user_service:8004"),
    "payment": os.getenv("PAYMENT_URL", "http://payment_service:8005"),
    "notification": os.getenv("NOTIFICATION_URL", "http://notification_service:8006"),
}

# Rate limiting (simple in-memory)
request_counts: Dict[str, Dict[str, int]] = {}
RATE_LIMIT = 100  # requests per minute per IP

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def check_rate_limit(client_ip: str) -> bool:
    current_time = int(time.time() // 60)  # per minute
    if client_ip not in request_counts:
        request_counts[client_ip] = {}

    if current_time not in request_counts[client_ip]:
        request_counts[client_ip][current_time] = 0

    if request_counts[client_ip][current_time] >= RATE_LIMIT:
        return False

    request_counts[client_ip][current_time] += 1
    return True

async def proxy_request(service_name: str, path: str, request: Request, method: str = "GET"):
    if service_name not in SERVICES:
        raise HTTPException(status_code=404, detail="Service not found")

    service_url = SERVICES[service_name]
    url = f"{service_url}{path}"

    # Get request data
    body = await request.body()
    headers = dict(request.headers)
    # Remove hop-by-hop headers
    headers.pop("host", None)

    # Simple retry-on-transient-error policy
    max_attempts = 2
    async with httpx.AsyncClient(timeout=30.0) as client:
        for attempt in range(1, max_attempts + 1):
            try:
                response = await client.request(
                    method=method,
                    url=url,
                    headers=headers,
                    content=body,
                    params=request.query_params,
                )

                # Retry on 5xx from downstream
                if 500 <= response.status_code < 600 and attempt < max_attempts:
                    logger.warning(f"Downstream {service_name} returned {response.status_code}; retrying (attempt {attempt})")
                    await __import__("asyncio").sleep(0.5 * (2 ** (attempt - 1)))
                    continue

                return JSONResponse(
                    status_code=response.status_code,
                    content=response.json() if response.headers.get("content-type") == "application/json" else response.text
                )
            except httpx.RequestError as e:
                logger.error(f"Request to {service_name} failed on attempt {attempt}: {e}")
                if attempt < max_attempts:
                    await __import__("asyncio").sleep(0.5 * (2 ** (attempt - 1)))
                    continue
                raise HTTPException(status_code=503, detail=f"Service {service_name} unavailable")

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    client_ip = request.client.host if request.client else "unknown"

    if not await check_rate_limit(client_ip):
        return JSONResponse(
            status_code=429,
            content={"detail": "Rate limit exceeded. Try again later."}
        )

    start_time = time.time()
    response = await call_next(request)
    process_time = time.time() - start_time

    # Log request
    logger.info(f"{request.method} {request.url.path} - {response.status_code} - {process_time:.3f}s - {client_ip}")

    return response

# Health check
@app.get("/health")
async def health_check():
    return {"status": "healthy", "gateway": "active"}

# Service routing


# Specific routes for better API design
@app.get("/api/routes/search")
async def search_routes(request: Request, source_station: str, destination_station: str, departure_date: str, preferences: Optional[str] = None):
    """Search for routes (proxy to route service using query params). This handler intentionally strips any
    incoming authentication-related headers before calling the route service so `/search` remains public.
    """
    service_url = SERVICES.get("route")
    logger.debug(f"SERVICES mapping: {SERVICES}")
    if not service_url:
        logger.error("Route service not found in SERVICES mapping")
        raise HTTPException(status_code=503, detail="Route service not available")

    params = {"source_station": source_station, "destination_station": destination_station, "departure_date": departure_date}
    if preferences:
        params["preferences"] = preferences

    # Build headers for downstream call but strip Authorization/Cookie to avoid accidental auth forwarding
    downstream_headers = {k: v for k, v in request.headers.items() if k.lower() not in ("authorization", "cookie")}

    import asyncio

    # retry-on-5xx policy for transient downstream errors
    max_attempts = 2
    async with httpx.AsyncClient(timeout=30.0) as client:
        for attempt in range(1, max_attempts + 1):
            try:
                resp = await client.get(f"{service_url}/search", params=params, headers=downstream_headers)
                # Log downstream response for debugging (helps trace unexpected 401/403 from downstream)
                content_type = resp.headers.get("content-type", "")
                body_preview = resp.text[:1000] if resp.text else ""
                logger.info(f"Route service responded: {resp.status_code} content-type={content_type} body_preview={body_preview} (attempt {attempt})")

                # If downstream incorrectly responds with an auth error, return a clearer gateway error
                if resp.status_code in (401, 403):
                    try:
                        err = resp.json()
                    except Exception:
                        err = {"detail": resp.text}

                    if err.get("detail") == "Not authenticated":
                        logger.warning("Downstream route service returned 'Not authenticated' for public /search endpoint")
                        raise HTTPException(status_code=502, detail="Downstream route service rejected anonymous access (check service configuration)")

                # For 5xx responses, optionally retry
                if 500 <= resp.status_code < 600 and attempt < max_attempts:
                    backoff = 0.5 * (2 ** (attempt - 1))
                    logger.warning(f"Downstream route service returned {resp.status_code}; retrying after {backoff}s (attempt {attempt})")
                    await asyncio.sleep(backoff)
                    continue

                return JSONResponse(status_code=resp.status_code, content=resp.json() if content_type.startswith("application/json") else resp.text)

            except httpx.RequestError as e:
                logger.error(f"Request to route service failed on attempt {attempt}: {e}")
                if attempt < max_attempts:
                    await asyncio.sleep(0.5 * (2 ** (attempt - 1)))
                    continue
                raise HTTPException(status_code=503, detail="Route service unavailable")

@app.post("/api/routes/optimize")
async def optimize_route(request: Request):
    """Optimize route using RL"""
    return await proxy_request("rl", "/optimize", request, "POST")

@app.post("/api/auth/login")
async def login(request: Request):
    """User login"""
    return await proxy_request("user", "/token", request, "POST")

@app.post("/api/auth/register")
async def register(request: Request):
    """User registration"""
    return await proxy_request("user", "/register", request, "POST")

@app.post("/api/payments/initiate")
async def initiate_payment(request: Request):
    """Initiate payment"""
    return await proxy_request("payment", "/initiate", request, "POST")

@app.post("/api/scraper/start")
async def start_scraping(request: Request):
    """Start web scraping"""
    return await proxy_request("scraper", "/scrape", request, "POST")



if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)