"""
RouteMaster — Quick startup verification.
Run this before starting the server to catch issues early.

    cd backend
    python verify.py
"""
import os, sys, asyncio, json, time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parent.parent))

# Load env
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

G = "\033[92m✅"
R = "\033[91m❌"
Y = "\033[93m⚠️ "
E = "\033[0m"

def ok(msg):  print(f"{G} {msg}{E}")
def fail(msg, err=None): print(f"{R} {msg}{f': {err}' if err else ''}{E}")
def warn(msg): print(f"{Y} {msg}{E}")

print("\n══════ RouteMaster Startup Verification ══════\n")

# 1. Python imports
print("── Core imports ──")
try:
    from fastapi import FastAPI; ok("FastAPI")
except ImportError as e: fail("FastAPI", e)

try:
    from sqlalchemy import text; ok("SQLAlchemy")
except ImportError as e: fail("SQLAlchemy", e)

try:
    import redis; ok("Redis client")
except ImportError as e: fail("Redis client", e)

try:
    import httpx; ok("httpx")
except ImportError as e: fail("httpx", e)

try:
    from passlib.context import CryptContext; ok("passlib (bcrypt)")
except ImportError as e: warn(f"passlib not installed: {e} — auth will fail")

try:
    from jose import jwt; ok("python-jose (JWT)")
except ImportError as e: warn(f"python-jose not installed: {e} — auth will fail")

# 2. Database
print("\n── Database (Supabase) ──")
async def check_db():
    db_url = os.getenv("DATABASE_URL", "")
    if not db_url:
        fail("DATABASE_URL not set in .env")
        return
    try:
        import asyncpg
        conn_url = db_url.replace("postgresql+asyncpg://", "postgresql://").replace("postgresql+psycopg2://", "postgresql://")
        conn = await asyncpg.connect(conn_url, ssl="require", timeout=10)
        count = await conn.fetchval("SELECT COUNT(*) FROM stops")
        await conn.close()
        if count and count > 0:
            ok(f"Supabase connected — {count:,} stations in stops table")
        else:
            warn(f"Supabase connected but stops table is empty ({count} rows)")
    except Exception as e:
        fail("Supabase connection", e)

asyncio.run(check_db())

# 3. Redis
print("\n── Redis (Upstash) ──")
try:
    import redis as rl
    redis_url = os.getenv("REDIS_URL", "")
    if not redis_url:
        warn("REDIS_URL not set — caching disabled")
    else:
        r = rl.from_url(redis_url, decode_responses=True, socket_connect_timeout=5)
        r.set("verify:ping", "ok", ex=60)
        val = r.get("verify:ping")
        if val == "ok":
            ok("Redis connected and writable")
        else:
            warn(f"Redis connected but read returned: {val}")
except Exception as e:
    fail("Redis", e)

# 4. Route engine data provider
print("\n── Route Engine (GTFS query) ──")
async def check_route_engine():
    try:
        from core.route_engine.data_provider import DataProvider
        dp = DataProvider()
        stop = dp.find_stop("NDLS")
        if stop:
            ok(f"find_stop('NDLS') → {stop.name}, {stop.city}")
            trains = dp.find_direct_trains("NDLS", "BCT", limit=3)
            if trains:
                ok(f"find_direct_trains(NDLS→BCT) → {len(trains)} trains found")
                t = trains[0]
                ok(f"  First: {t.route_id} '{t.train_name}' dep={t.departure_time} arr={t.arrival_time}")
            else:
                warn("find_direct_trains returned 0 results — DB may have data issues")
        else:
            warn("find_stop('NDLS') returned None — check if stops.code='NDLS' exists in DB")
            # Try to find what codes DO exist
            from sqlalchemy import text
            session = dp.session
            sample = session.execute(text("SELECT code, name FROM stops ORDER BY is_major_junction DESC LIMIT 5")).fetchall()
            warn(f"  Sample stop codes in DB: {[r[0] for r in sample]}")
        dp.close()
    except Exception as e:
        fail("Route engine", e)

asyncio.run(check_route_engine())

# 5. API v1 imports
print("\n── API v1 imports ──")
for mod in ["api.v1.search", "api.v1.stations", "api.v1.auth", "api.v1.live", "api.v1.pnr", "api.v1.sos"]:
    try:
        import importlib
        importlib.import_module(mod)
        ok(f"{mod}")
    except Exception as e:
        fail(f"{mod}", e)

# 6. RapidAPI
print("\n── RapidAPI ──")
rapidapi_key = os.getenv("RAPIDAPI_KEY", "")
if not rapidapi_key:
    warn("RAPIDAPI_KEY not set — live status and PNR will not work")
    print("   → Get free key at: https://rapidapi.com/search/indian-railway")
else:
    ok(f"RAPIDAPI_KEY set (length {len(rapidapi_key)})")

# 7. JWT secret
print("\n── Auth config ──")
jwt_secret = os.getenv("JWT_SECRET", "")
if not jwt_secret:
    warn("JWT_SECRET not set — using insecure default. Set it in .env for production.")
else:
    ok("JWT_SECRET configured")

print("\n══════════════════════════════════════════════")
print("To start the server:")
print("  uvicorn app:app --reload --port 8000")
print("")
print("Endpoints to test after startup:")
print("  GET  http://localhost:8000/health")
print("  GET  http://localhost:8000/api/v1/stations/suggest?q=delhi")
print("  GET  http://localhost:8000/api/v1/search/routes?source=NDLS&destination=BCT&date=2026-06-10")
print("  GET  http://localhost:8000/docs  ← Full API docs")
print()
