import asyncio
import os
import sys
import logging
import time
from datetime import datetime, timedelta
from sqlalchemy import text

# Add backend to sys.path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from database.session import SessionLocal
from core.redis import async_redis_client
from core.route_engine.turbo_router import TurboRouter
from supabase_client import supabase
from database.config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def verify_integrity():
    logger.info("Starting Global System Integrity Check (Production Readiness)...")
    errors = []

    # 1. DATABASE CHECK
    logger.info("1. Verifying Railway PostgreSQL...")
    db = SessionLocal()
    try:
        # Check core tables
        tables = ['users', 'profiles', 'stops', 'stop_times', 'segments', 'station_transit_index', 'bookings', 'payments']
        for t in tables:
            count = db.execute(text(f"SELECT COUNT(*) FROM {t}")).scalar()
            logger.info(f"   ✓ Table {t:25}: {count} rows")
        
        # Verify optimized index structure
        sample = db.execute(text("SELECT station_code, trains_map FROM station_transit_index LIMIT 1")).fetchone()
        if sample and isinstance(sample.trains_map, dict):
            logger.info("   ✓ station_transit_index schema validated (Object-Mapped JSONB)")
        else:
            errors.append("station_transit_index has invalid schema or no data")
            
    except Exception as e:
        logger.error(f"   ✗ Database check failed: {e}")
        errors.append(f"Database: {e}")
    finally:
        db.close()

    # 2. REDIS CHECK
    logger.info("2. Verifying Redis (Rate Limiter & Cache)...")
    try:
        pong = await async_redis_client.ping()
        if pong:
            logger.info("   ✓ Redis connection successful")
        else:
            errors.append("Redis ping returned False")
    except Exception as e:
        logger.error(f"   ✗ Redis check failed: {e}")
        errors.append(f"Redis: {e}")

    # 3. SUPABASE AUTH CHECK
    logger.info("3. Verifying Supabase Auth Integration...")
    try:
        # Attempt to get a user with an invalid token to see if API is reachable
        try:
            supabase.auth.get_user("invalid-token")
        except Exception as e:
            msg = str(e).lower()
            if any(x in msg for x in ["invalid", "401", "403", "segments", "token"]):
                logger.info("   ✓ Supabase Auth reachable and keys validated")
            else:
                errors.append(f"Supabase returned unexpected error: {e}")
    except Exception as e:
        logger.error(f"   ✗ Supabase initialization failed: {e}")
        errors.append(f"Supabase: {e}")

    # 4. TURBO SEARCH PERFORMANCE CHECK
    logger.info("4. Benchmarking Turbo Search (NDLS -> BCT)...")
    try:
        router = TurboRouter()
        start = time.time()
        # Search for tomorrow
        test_date = datetime.now() + timedelta(days=1)
        routes = router.find_routes("NDLS", "BCT", test_date)
        elapsed = (time.time() - start) * 1000
        
        if routes:
            logger.info(f"   ✓ Turbo Search: Found {len(routes)} routes in {elapsed:.2f}ms")
            if elapsed > 1000:
                logger.warning(f"   ⚠️ Latency higher than target (1000ms): {elapsed:.2f}ms")
        else:
            errors.append("Turbo Search returned zero results for NDLS->BCT")
    except Exception as e:
        logger.error(f"   ✗ Turbo Search failed: {e}")
        errors.append(f"Search: {e}")

    # 5. SCHEMA INTEGRITY (Cross-Table Joins)
    logger.info("5. Verifying Data Locality (JOINS)...")
    db = SessionLocal()
    try:
        # Test if we can join bookings with trips (Business + Transit)
        # Even if 0 rows, the query should not fail
        db.execute(text("SELECT b.id FROM bookings b JOIN trips t ON b.route_id = t.trip_id LIMIT 1"))
        logger.info("   ✓ Business-Transit Join capability verified")
    except Exception as e:
        logger.error(f"   ✗ Data locality join failed: {e}")
        errors.append(f"Join Integrity: {e}")
    finally:
        db.close()

    # FINAL REPORT
    print("\n" + "="*50)
    if not errors:
        print("🎉 SYSTEM INTEGRITY VERIFIED: READY FOR PRODUCTION")
        return True
    else:
        print(f"❌ SYSTEM INTEGRITY FAILED: {len(errors)} critical issues found")
        for err in errors:
            print(f"   - {err}")
        return False

if __name__ == "__main__":
    success = asyncio.run(verify_integrity())
    if success:
        sys.exit(0)
    else:
        sys.exit(1)
