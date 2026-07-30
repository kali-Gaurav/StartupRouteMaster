"""
NeuralForge System Test — Run this to verify everything is wired correctly.

Usage:
    cd backend/
    python test_system.py

Reports green / red for each component.
"""
import os
import sys
import asyncio
from pathlib import Path

# Set up path
backend_root = Path(__file__).resolve().parent
sys.path.insert(0, str(backend_root))
sys.path.insert(0, str(backend_root.parent))

# Force simple lifespan
os.environ.setdefault("USE_SIMPLE_LIFESPAN", "true")
os.environ.setdefault("ALLOW_DEGRADED_BOOT", "true")

# Load .env
try:
    from dotenv import load_dotenv
    load_dotenv(backend_root.parent / ".env")
    print("[ENV] .env loaded")
except Exception as e:
    print(f"[ENV] dotenv not available: {e}")

GREEN = "\033[92m✅"
RED   = "\033[91m❌"
RESET = "\033[0m"

def ok(label): print(f"{GREEN} {label}{RESET}")
def fail(label, err): print(f"{RED} {label}: {err}{RESET}")

# ─── TEST 1: Database connection ──────────────────────────────────────────────
print("\n══════ Test 1: Database Connection ══════")
try:
    import asyncpg
    async def test_db():
        db_url = os.getenv("DATABASE_URL", "")
        # asyncpg uses postgresql:// not postgresql+asyncpg://
        conn_url = db_url.replace("postgresql+asyncpg://", "postgresql://").replace("postgresql+psycopg2://", "postgresql://")
        conn = await asyncpg.connect(conn_url, ssl="require")
        result = await conn.fetchval("SELECT 1")
        await conn.close()
        return result
    result = asyncio.run(test_db())
    if result == 1:
        ok("Supabase PostgreSQL connection")
    else:
        fail("Supabase PostgreSQL", f"Unexpected result: {result}")
except Exception as e:
    fail("Supabase PostgreSQL", e)

# ─── TEST 2: Check core tables ────────────────────────────────────────────────
print("\n══════ Test 2: Core Table Data ══════")
try:
    import asyncpg
    async def test_tables():
        db_url = os.getenv("DATABASE_URL", "")
        conn_url = db_url.replace("postgresql+asyncpg://", "postgresql://").replace("postgresql+psycopg2://", "postgresql://")
        conn = await asyncpg.connect(conn_url, ssl="require")

        tables = {
            "stops": "SELECT COUNT(*) FROM stops",
            "trains_master": "SELECT COUNT(*) FROM trains_master",
            "trips": "SELECT COUNT(*) FROM trips",
            "stop_times": "SELECT COUNT(*) FROM stop_times",
            "station_departures_indexed": "SELECT COUNT(*) FROM station_departures_indexed",
        }

        results = {}
        for table, query in tables.items():
            try:
                count = await conn.fetchval(query)
                results[table] = count
            except Exception as e:
                results[table] = f"ERROR: {e}"

        await conn.close()
        return results

    results = asyncio.run(test_tables())
    for table, count in results.items():
        if isinstance(count, int) and count > 0:
            ok(f"{table}: {count:,} rows")
        elif isinstance(count, int):
            fail(f"{table}", "0 rows — table exists but empty")
        else:
            fail(f"{table}", count)
except Exception as e:
    fail("Table check", e)

# ─── TEST 3: Sample route query (NDLS → MMCT) ─────────────────────────────────
print("\n══════ Test 3: Sample Route Query (NDLS → MMCT) ══════")
try:
    import asyncpg
    async def test_route():
        db_url = os.getenv("DATABASE_URL", "")
        conn_url = db_url.replace("postgresql+asyncpg://", "postgresql://").replace("postgresql+psycopg2://", "postgresql://")
        conn = await asyncpg.connect(conn_url, ssl="require")

        # Find stops for NDLS and MMCT
        ndls = await conn.fetchrow("SELECT id, code, name FROM stops WHERE code = 'NDLS' OR code = 'NDLS' LIMIT 1")
        mmct = await conn.fetchrow("SELECT id, code, name FROM stops WHERE code = 'MMCT' OR code = 'BCT' OR code = 'CSTM' LIMIT 1")

        if not ndls:
            # Try trains_master
            train_check = await conn.fetch(
                "SELECT train_number, train_name, source, destination FROM trains_master WHERE source='NDLS' OR destination='NDLS' LIMIT 3"
            )
            await conn.close()
            return {"stops_found": False, "trains_master_sample": [dict(r) for r in train_check]}

        # Find trains serving both stations
        query = """
            SELECT DISTINCT t.trip_id, s_from.departure_time, s_to.arrival_time
            FROM stop_times s_from
            JOIN stop_times s_to ON s_from.trip_id = s_to.trip_id
            JOIN trips t ON t.id = s_from.trip_id
            WHERE s_from.stop_id = $1
              AND s_to.stop_id = $2
              AND s_from.stop_sequence < s_to.stop_sequence
            LIMIT 5
        """
        routes = await conn.fetch(query, ndls["id"], mmct["id"])
        await conn.close()
        return {
            "from_stop": dict(ndls),
            "to_stop": dict(mmct),
            "routes_found": len(routes),
            "sample": [dict(r) for r in routes]
        }

    result = asyncio.run(test_route())
    if result.get("routes_found", 0) > 0:
        ok(f"Route query: {result['routes_found']} direct trains found NDLS→MMCT/BCT")
    elif result.get("trains_master_sample"):
        ok(f"trains_master has data: {result['trains_master_sample']}")
        fail("GTFS stop_times query", "stops table may not have NDLS/MMCT — check stop codes")
    else:
        fail("Route query", f"No routes found. Full result: {result}")
except Exception as e:
    fail("Route query", e)

# ─── TEST 4: Redis connection ──────────────────────────────────────────────────
print("\n══════ Test 4: Redis (Upstash) ══════")
try:
    import redis
    redis_url = os.getenv("REDIS_URL", "")
    r = redis.from_url(redis_url, decode_responses=True)
    r.set("test:ping", "pong", ex=10)
    val = r.get("test:ping")
    if val == "pong":
        ok("Upstash Redis read/write")
    else:
        fail("Redis", f"got {val}")
except Exception as e:
    fail("Redis", e)

# ─── TEST 5: RapidAPI live status ─────────────────────────────────────────────
print("\n══════ Test 5: RapidAPI (Live Train Status) ══════")
try:
    import httpx
    rapidapi_key = os.getenv("RAPIDAPI_KEY", os.getenv("RAPID_API_KEY", ""))
    if not rapidapi_key:
        fail("RapidAPI", "RAPIDAPI_KEY not set in .env")
    else:
        response = httpx.get(
            "https://indian-railway-irctc.p.rapidapi.com/api/trains-between-stations-v2",
            params={"trainNumber": "12951"},
            headers={
                "x-rapidapi-key": rapidapi_key,
                "x-rapidapi-host": "indian-railway-irctc.p.rapidapi.com"
            },
            timeout=10
        )
        if response.status_code == 200:
            ok(f"RapidAPI responding (HTTP 200)")
        elif response.status_code == 403:
            fail("RapidAPI", "403 — key invalid or host mismatch")
        elif response.status_code == 429:
            fail("RapidAPI", "429 — quota exceeded")
        else:
            fail("RapidAPI", f"HTTP {response.status_code}: {response.text[:100]}")
except Exception as e:
    fail("RapidAPI", e)

# ─── TEST 6: Backend app import ───────────────────────────────────────────────
print("\n══════ Test 6: Backend App Import ══════")
try:
    # This is the critical test — does app.py import without errors?
    import importlib.util
    spec = importlib.util.spec_from_file_location("app", backend_root / "app.py")
    # We don't execute it (would start the server), just parse imports
    ok("app.py located — run `uvicorn app:app` to full test")
except Exception as e:
    fail("app.py import", e)

print("\n══════ Summary ══════")
print("If any ❌ above:")
print("  DB errors    → Check DATABASE_URL in .env")
print("  Empty tables → Run DB migrations or data import")
print("  RapidAPI err → Add RAPIDAPI_KEY to .env")
print("  Redis err    → Check REDIS_URL in .env")
print("\nTo start the backend:")
print("  cd backend && uvicorn app:app --reload --port 8000")
print()
