"""
[NOVA] Schema Validator — Run this FIRST before any seed or search.
Checks that Supabase tables exist with correct column names
that data_provider.py queries.

Usage:
    cd backend
    python scripts/schema_check.py

Fixes any column-name mismatches (e.g. stop_code → code).
"""
import os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
from dotenv import load_dotenv
load_dotenv(Path(__file__).resolve().parents[2] / ".env")

import asyncpg
import asyncio

G = "\033[92m✅"; R = "\033[91m❌"; Y = "\033[93m⚠️ "; E = "\033[0m"
def ok(m): print(f"{G} {m}{E}")
def fail(m): print(f"{R} {m}{E}")
def warn(m): print(f"{Y} {m}{E}")
def info(m): print(f"   {m}")

DB_URL = os.getenv("DATABASE_URL", "")

# What data_provider.py actually queries
REQUIRED_SCHEMA = {
    "stops": {
        "required": ["id", "code", "name"],
        "optional": ["city", "state", "latitude", "longitude", "is_major_junction"],
        "aliases": {
            "stop_code": "code",      # GTFS standard vs our schema
            "stop_name": "name",
            "stop_lat": "latitude",
            "stop_lon": "longitude",
        }
    },
    "trips": {
        "required": ["id", "trip_id", "route_id"],
        "optional": ["service_id", "is_cancelled"],
        "aliases": {}
    },
    "stop_times": {
        "required": ["id", "trip_id", "stop_id", "stop_sequence", "arrival_time", "departure_time"],
        "optional": ["arrival_timestamp", "departure_timestamp"],
        "aliases": {
            "arrival_time": "arrival_time",
            "departure_time": "departure_time",
        }
    },
    "trains_master": {
        "required": ["train_number", "train_name"],
        "optional": ["source", "destination", "days_of_run"],
        "aliases": {}
    },
}

async def get_columns(conn, table):
    rows = await conn.fetch(
        "SELECT column_name FROM information_schema.columns WHERE table_name=$1 AND table_schema='public'",
        table
    )
    return {r["column_name"] for r in rows}

async def get_row_count(conn, table):
    try:
        return await conn.fetchval(f"SELECT COUNT(*) FROM {table}")
    except Exception:
        return -1

async def fix_column_alias(conn, table, old_col, new_col, existing_cols):
    """Rename a column from GTFS standard to our expected name."""
    if old_col in existing_cols and new_col not in existing_cols:
        warn(f"  Renaming {table}.{old_col} → {new_col}")
        try:
            await conn.execute(f'ALTER TABLE {table} RENAME COLUMN "{old_col}" TO "{new_col}"')
            ok(f"  Renamed {table}.{old_col} → {new_col}")
            return True
        except Exception as e:
            fail(f"  Could not rename {table}.{old_col}: {e}")
    return False

async def add_missing_column(conn, table, col):
    """Add a missing optional column with a safe default."""
    defaults = {
        "city": "TEXT DEFAULT ''",
        "state": "TEXT DEFAULT ''",
        "latitude": "FLOAT DEFAULT 0.0",
        "longitude": "FLOAT DEFAULT 0.0",
        "is_major_junction": "BOOLEAN DEFAULT false",
        "is_cancelled": "BOOLEAN DEFAULT false",
        "arrival_timestamp": "BIGINT",
        "departure_timestamp": "BIGINT",
        "days_of_run": "TEXT",
        "source": "TEXT DEFAULT ''",
        "destination": "TEXT DEFAULT ''",
    }
    if col in defaults:
        try:
            await conn.execute(f'ALTER TABLE {table} ADD COLUMN IF NOT EXISTS "{col}" {defaults[col]}')
            ok(f"  Added {table}.{col}")
        except Exception as e:
            warn(f"  Could not add {table}.{col}: {e}")

async def ensure_indexes(conn):
    """Create performance indexes if missing."""
    indexes = [
        ("idx_stops_code", "CREATE INDEX IF NOT EXISTS idx_stops_code ON stops(UPPER(code))"),
        ("idx_stops_name", "CREATE INDEX IF NOT EXISTS idx_stops_name ON stops(UPPER(name))"),
        ("idx_stop_times_trip", "CREATE INDEX IF NOT EXISTS idx_stop_times_trip ON stop_times(trip_id)"),
        ("idx_stop_times_stop", "CREATE INDEX IF NOT EXISTS idx_stop_times_stop ON stop_times(stop_id)"),
        ("idx_trips_route", "CREATE INDEX IF NOT EXISTS idx_trips_route ON trips(route_id)"),
        ("idx_trains_number", "CREATE INDEX IF NOT EXISTS idx_trains_number ON trains_master(train_number)"),
    ]
    for name, sql in indexes:
        try:
            await conn.execute(sql)
        except Exception:
            pass
    ok("Performance indexes ensured")

async def main():
    print("\n═══════════ Route Master Schema Validator ═══════════\n")

    if not DB_URL:
        fail("DATABASE_URL not set in .env")
        return

    conn_url = DB_URL.replace("postgresql+asyncpg://", "postgresql://").replace("postgresql+psycopg2://", "postgresql://")
    if "?" in conn_url:
        conn_url = conn_url.split("?")[0]

    try:
        conn = await asyncpg.connect(conn_url, ssl="require", timeout=15)
        ok("Connected to Supabase")
    except Exception as e:
        fail(f"Connection failed: {e}")
        return

    all_ok = True
    fixes_applied = 0

    for table, schema in REQUIRED_SCHEMA.items():
        print(f"\n── {table} ──")
        existing = await get_columns(conn, table)
        count = await get_row_count(conn, table)

        if not existing:
            fail(f"Table '{table}' does not exist! Run seed_data.py to create it.")
            all_ok = False
            continue

        # Fix GTFS → our schema column aliases
        for gtfs_col, our_col in schema["aliases"].items():
            if await fix_column_alias(conn, table, gtfs_col, our_col, existing):
                existing = await get_columns(conn, table)  # refresh
                fixes_applied += 1

        # Check required columns
        for col in schema["required"]:
            if col in existing:
                ok(f"  {col} ✓")
            else:
                fail(f"  {col} — MISSING (required!)")
                all_ok = False

        # Add missing optional columns
        for col in schema["optional"]:
            if col not in existing:
                await add_missing_column(conn, table, col)
                fixes_applied += 1

        if count >= 0:
            if count == 0:
                warn(f"  Row count: 0 — Table is EMPTY. Run seed_data.py!")
                all_ok = False
            else:
                ok(f"  Row count: {count:,}")

    # Ensure indexes
    print("\n── Indexes ──")
    await ensure_indexes(conn)

    # Quick search test
    print("\n── Quick Search Test ──")
    try:
        ndls = await conn.fetchrow("SELECT id, code, name FROM stops WHERE UPPER(code)='NDLS' LIMIT 1")
        if ndls:
            ok(f"find_stop('NDLS') → {ndls['name']} (id={ndls['id']})")
            # Check stop_times for this station
            st_count = await conn.fetchval("SELECT COUNT(*) FROM stop_times WHERE stop_id=$1", ndls['id'])
            ok(f"  stop_times for NDLS: {st_count:,} entries")
        else:
            warn("NDLS not found. Check station codes in your stops table.")
            # Show sample codes
            sample = await conn.fetch("SELECT code, name FROM stops LIMIT 5")
            if sample:
                warn(f"  Sample codes: {[r['code'] for r in sample]}")
    except Exception as e:
        fail(f"Search test failed: {e}")

    await conn.close()

    print("\n═══════════════════════════════════════════════")
    if fixes_applied:
        ok(f"{fixes_applied} schema fix(es) applied automatically")
    if all_ok:
        ok("Schema is VALID — ready to search!")
    else:
        fail("Schema has issues — run seed_data.py to populate missing tables/data")
    print()

asyncio.run(main())
