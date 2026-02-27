import asyncio
import logging
import os
import sqlite3
import redis.asyncio as aioredis
from datetime import datetime
import httpx
from sqlalchemy import text

# Configure logging
logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger("verify_system")
logging.getLogger("core.route_engine").setLevel(logging.DEBUG)

# Set PYTHONPATH
import sys
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from database.config import Config
from database.session import SessionLocal, init_db, engine_write
from database.models import Stop, Trip

async def test_supabase_connection():
    logger.info("--- Testing Supabase Connection ---")
    try:
        from supabase_client import supabase
        resp = supabase.from_("profiles").select("id").limit(1).execute()
        if hasattr(resp, "error") and resp.error:
            logger.error(f"Supabase query failed: {resp.error}")
            return False
        logger.info("✅ Supabase connection successful.")
        return True
    except Exception as e:
        logger.error(f"❌ Supabase connection failed: {e}")
        return False

async def test_redis_connection():
    logger.info("--- Testing Redis Connection ---")
    try:
        r = aioredis.from_url(Config.REDIS_URL)
        await r.ping()
        logger.info("✅ Redis connection successful.")
        await r.aclose()
        return True
    except Exception as e:
        logger.error(f"❌ Redis connection failed: {e}")
        return False

async def test_rapidapi_connection():
    logger.info("--- Testing RapidAPI Connection ---")
    if not Config.RAPIDAPI_KEY:
        logger.warning("⚠️ RAPIDAPI_KEY not found in Config.")
        return False
    
    try:
        url = f"https://{Config.RAPIDAPI_HOST}/api/v1/getFare"
        headers = {
            "x-rapidapi-key": Config.RAPIDAPI_KEY,
            "x-rapidapi-host": Config.RAPIDAPI_HOST
        }
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, headers=headers, params={"trainNo": "12951", "fromStationCode": "NDLS", "toStationCode": "MMCT"}, timeout=5)
            if resp.status_code == 200:
                logger.info("✅ RapidAPI connection successful.")
                return True
            else:
                logger.warning(f"⚠️ RapidAPI returned status {resp.status_code}")
                return resp.status_code != 401
    except Exception as e:
        logger.error(f"❌ RapidAPI connection failed: {e}")
        return False

def verify_sqlite_files():
    logger.info("--- Verifying SQLite Database Files ---")
    files = {
        "railway_data.db": "backend/database/railway_data.db",
        "transit_graph.db": "backend/database/transit_graph.db"
    }
    
    all_ok = True
    for name, path in files.items():
        if not os.path.exists(path):
            logger.error(f"❌ {name} NOT FOUND at {path}")
            all_ok = False
            continue
        try:
            conn = sqlite3.connect(path)
            cursor = conn.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' LIMIT 1;")
            table = cursor.fetchone()
            if table:
                logger.info(f"✅ {name} verified (found table: {table[0]})")
            else:
                logger.warning(f"⚠️ {name} verified but is EMPTY")
            conn.close()
        except Exception as e:
            logger.error(f"❌ {name} connection failed: {e}")
            all_ok = False
    return all_ok

async def test_route_engine():
    logger.info("--- Testing Route Engine & Graph Building ---")
    try:
        from core.route_engine import RailwayRouteEngine
        engine = RailwayRouteEngine()
        
        session = SessionLocal()
        stops_count = session.query(Stop).count()
        trips_count = session.query(Trip).count()
        logger.info(f"Database Stats (from current engine): Stops={stops_count}, Trips={trips_count}")
        
        ndls = session.query(Stop).filter(Stop.stop_id == "NDLS").first()
        mmct = session.query(Stop).filter(Stop.stop_id == "MMCT").first()
        logger.info(f"Stop Check: NDLS={ndls is not None}, MMCT={mmct is not None}")
        
        session.close()
        
        logger.info("Performing sample route search (NDLS -> BCT at 8 AM)...")
        search_date = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)
        routes = await engine.search_routes("NDLS", "BCT", search_date)
        
        if routes:
            logger.info(f"✅ Route search successful! Found {len(routes)} routes.")
        else:
            logger.warning("⚠️ Route search returned 0 results.")
            
        return True
    except Exception as e:
        logger.error(f"❌ Route Engine test failed: {e}")
        return False

async def main():
    logger.info("Starting System Verification...")
    
    try:
        Config.validate()
        logger.info("✅ Config validation passed.")
    except Exception as e:
        logger.error(f"❌ Config validation failed: {e}")
    
    sqlite_ok = verify_sqlite_files()
    supabase_ok = await test_supabase_connection()
    redis_ok = await test_redis_connection()
    rapid_ok = await test_rapidapi_connection()
    
    # Check if Postgres is actually what we think it is
    pg_verified = False
    try:
        dialect = engine_write.dialect.name
        logger.info(f"Active database dialect: {dialect}")
        if dialect == "postgresql":
            pg_verified = True
            logger.info("✅ Primary engine is indeed POSTGRESQL.")
        else:
            logger.warning(f"⚠️ Primary engine is NOT Postgres (it is {dialect}). Check connectivity!")
    except Exception as e:
        logger.error(f"Could not verify database dialect: {e}")

    engine_ok = await test_route_engine()
    
    print("\n" + "="*30)
    print("VERIFICATION SUMMARY")
    print("="*30)
    print(f"SQLite Files:    {'OK' if sqlite_ok else 'FAILED'}")
    print(f"Supabase:        {'OK' if supabase_ok else 'FAILED'}")
    print(f"Redis:           {'OK' if redis_ok else 'FAILED'}")
    print(f"RapidAPI:        {'OK' if rapid_ok else 'FAILED'}")
    print(f"Postgres (Real): {'OK' if pg_verified else 'FAILED'}")
    print(f"Route Engine:    {'OK' if engine_ok else 'FAILED'}")
    print("="*30)

if __name__ == "__main__":
    asyncio.run(main())
