#!/usr/bin/env python3
"""
Mock RouteMaster API Server for Concurrency Testing
==================================================

Simple FastAPI server that mimics the RouteMaster API for load testing.
No database or Redis dependencies - just returns mock responses.
"""

import asyncio
import time
import random
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import uvicorn

app = FastAPI(title="Mock RouteMaster API", version="1.0.0")

class RouteSearchRequest(BaseModel):
    origin: str
    destination: str
    date: str
    passengers: Optional[int] = 1
    classes: Optional[List[str]] = None
    flexible_dates: Optional[bool] = False

class RouteOption(BaseModel):
    train_number: str
    train_name: str
    departure_time: str
    arrival_time: str
    duration: str
    classes: List[Dict[str, Any]]
    price_range: Dict[str, float]

class RouteSearchResponse(BaseModel):
    routes: List[RouteOption]
    search_id: str
    total_found: int

# Mock data for realistic responses
MOCK_TRAINS = [
    {"number": "12951", "name": "Rajdhani Express", "speed": "fast"},
    {"number": "12245", "name": "Duronto Express", "speed": "fast"},
    {"number": "12627", "name": "Karnataka Express", "speed": "medium"},
    {"number": "11057", "name": "Pathankot Express", "speed": "slow"},
    {"number": "12138", "name": "Punjab Mail", "speed": "medium"},
    {"number": "12859", "name": "Gitanjali Express", "speed": "fast"},
    {"number": "12301", "name": "Kolkata Rajdhani", "speed": "fast"},
    {"number": "12423", "name": "Dibrugarh Rajdhani", "speed": "fast"},
]

MOCK_STATIONS = {
    "NDLS": "New Delhi",
    "BCT": "Mumbai Central",
    "SBC": "Bangalore City",
    "MAS": "Chennai Central",
    "HWH": "Howrah Junction",
    "PUNE": "Pune Junction",
    "LKO": "Lucknow",
    "BPL": "Bhopal",
    "AGC": "Agra Cantt",
    "JAT": "Jammu Tawi"
}

def generate_mock_route(origin: str, destination: str, date: str) -> RouteOption:
    """Generate a realistic mock route"""
    train = random.choice(MOCK_TRAINS)

    # Generate realistic times
    dep_hour = random.randint(6, 22)  # 6 AM to 10 PM
    dep_minute = random.randint(0, 59)
    duration_hours = random.randint(4, 24)  # 4 to 24 hours

    dep_time = f"{dep_hour:02d}:{dep_minute:02d}"
    arr_hour = (dep_hour + duration_hours) % 24
    arr_minute = (dep_minute + random.randint(0, 59)) % 60
    arr_time = f"{arr_hour:02d}:{arr_minute:02d}"

    duration = f"{duration_hours}h {(dep_minute + 30) % 60}m"  # Approximate

    # Generate classes with prices
    classes = []
    base_price = random.randint(500, 3000)

    for class_type in ["1A", "2A", "3A", "SL", "CC"]:
        if random.random() > 0.3:  # 70% chance of having this class
            multiplier = {"1A": 4.0, "2A": 2.5, "3A": 1.8, "SL": 1.0, "CC": 1.2}[class_type]
            price = base_price * multiplier
            availability = random.randint(0, 50)

            classes.append({
                "class": class_type,
                "price": round(price, 2),
                "availability": availability,
                "status": "AVAILABLE" if availability > 0 else "WAITLIST"
            })

    return RouteOption(
        train_number=train["number"],
        train_name=train["name"],
        departure_time=dep_time,
        arrival_time=arr_time,
        duration=duration,
        classes=classes,
        price_range={
            "min": min(c["price"] for c in classes) if classes else 0,
            "max": max(c["price"] for c in classes) if classes else 0
        }
    )

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "service": "mock_routemaster_api"}

@app.post("/api/routes/search")
async def search_routes(request: RouteSearchRequest):
    """
    Mock route search endpoint

    Simulates realistic API behavior:
    - Variable response times (50-500ms)
    - Occasional failures (1% error rate)
    - Realistic route data
    """
    # Simulate processing time
    processing_time = random.uniform(0.05, 0.5)  # 50-500ms
    await asyncio.sleep(processing_time)

    # Simulate occasional failures (1% error rate)
    if random.random() < 0.01:
        raise HTTPException(status_code=500, detail="Internal server error")

    # Validate stations
    if request.origin not in MOCK_STATIONS or request.destination not in MOCK_STATIONS:
        raise HTTPException(status_code=400, detail="Invalid station code")

    # Generate 3-8 mock routes
    num_routes = random.randint(3, 8)
    routes = []

    for _ in range(num_routes):
        route = generate_mock_route(request.origin, request.destination, request.date)
        routes.append(route)

    # Filter by requested classes if specified
    if request.classes:
        for route in routes:
            route.classes = [c for c in route.classes if c["class"] in request.classes]

    response = RouteSearchResponse(
        routes=routes,
        search_id=f"search_{int(time.time())}_{random.randint(1000, 9999)}",
        total_found=len(routes)
    )

    return response

@app.get("/metrics")
async def metrics():
    """Prometheus-style metrics endpoint"""
    return {
        "requests_total": 1000,
        "requests_failed": 10,
        "avg_response_time": 0.25,
        "uptime_seconds": 3600
    }

if __name__ == "__main__":
    print("🚀 Starting Mock RouteMaster API Server")
    print("📍 Server will run on http://localhost:8000")
    print("🎯 Ready for concurrency testing")
    print("💡 Mock responses simulate realistic railway search API")

    uvicorn.run(
        app,
        host="localhost",
        port=8000,
        log_level="info"
    )