import asyncio
import os
import httpx
import logging
import sys
from datetime import datetime
from sqlalchemy import text

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from dotenv import load_dotenv
load_dotenv("backend/.env")

from database.session import SessionLocal, engine
from core.redis import async_redis_client
from database.config import Config

logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger("PROD_AUDIT")

async def run_audit():
    errors = []
    print("\n🔍 --- MASTER PRODUCTION AUDIT STARTING ---")

    # 1. DATABASE AUDIT (Railway/Postgres)
    print("\n1. Auditing Database (Railway/Postgres)...")
    db = SessionLocal()
    try:
        # Check core tables
        required_tables = [
            "users", "train_availability_cache", "booking_requests", 
            "unlocked_routes", "payment_sessions", "stations"
        ]
        for table in required_tables:
            try:
                result = db.execute(text(f"SELECT count(*) FROM {table}")).fetchone()
                print(f"   ✅ Table '{table}' exists (Rows: {result[0]})")
            except Exception as te:
                print(f"   ❌ Table '{table}' MISSING or ERROR: {te}")
                errors.append(f"Table {table}: {te}")
        
        # Check specific columns for Phase 2 readiness
        try:
            db.execute(text("SELECT status_text, seats_available, fare FROM train_availability_cache LIMIT 1"))
            print("   ✅ TrainAvailabilityCache schema verified (Seats/Fare/Status present)")
        except Exception as se:
            print(f"   ❌ TrainAvailabilityCache schema INVALID: {se}")
            errors.append(f"Schema: {se}")

    except Exception as e:
        print(f"   ❌ DB AUDIT FAILED: {e}")
        errors.append(f"DB: {e}")
    finally:
        db.close()

    # 2. REDIS AUDIT (Upstash)
    print("\n2. Auditing Cache (Upstash/Redis)...")
    try:
        await async_redis_client.ping()
        keys = await async_redis_client.keys("availability:*")
        print(f"   ✅ Redis connected. Found {len(keys)} active availability cache keys.")
        
        # Test write/read
        await async_redis_client.set("audit_test", "ok", ex=10)
        test_val = await async_redis_client.get("audit_test")
        if test_val == "ok":
            print("   ✅ Redis Read/Write verified.")
        else:
            print(f"   ❌ Redis Read/Write failed. Got: {test_val}")
            errors.append("Redis: Read/Write failure")
    except Exception as e:
        print(f"   ❌ REDIS AUDIT FAILED: {e}")
        errors.append(f"Redis: {e}")

    # 3. BACKEND API ENDPOINT AUDIT (FastAPI)
    print("\n3. Auditing Backend API Endpoints (Port 8000)...")
    async with httpx.AsyncClient(timeout=10.0) as client:
        endpoints = [
            ("/", 200),
            ("/ping", 200),
            ("/api/stations/search?q=KOTA", 200),
        ]
        for path, expected_status in endpoints:
            try:
                resp = await client.get(f"http://localhost:8000{path}")
                if resp.status_code == expected_status:
                    print(f"   ✅ GET {path} -> {resp.status_code}")
                else:
                    print(f"   ⚠️ GET {path} -> {resp.status_code} (Expected {expected_status})")
            except Exception as e:
                print(f"   ❌ Endpoint {path} unreachable: {e}")
                errors.append(f"API {path}: {e}")

    # 4. FRONTEND CONNECTIVITY AUDIT (Vite)
    print("\n4. Auditing Frontend Connectivity (Port 5173)...")
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.get("http://localhost:5173")
            if resp.status_code == 200:
                print(f"   ✅ Frontend is serving on Port 5173")
            else:
                print(f"   ⚠️ Frontend returned status {resp.status_code}")
        except Exception as e:
            print(f"   ❌ Frontend unreachable: {e}")
            errors.append(f"Frontend: {e}")

    # 5. CONFIGURATION CONSISTENCY
    print("\n5. Auditing Configuration...")
    try:
        # Check backend env
        if os.getenv("RAPID_API_KEY"):
            print("   ✅ RAPID_API_KEY present.")
        else:
            print("   ⚠️ WARNING: RAPID_API_KEY missing.")
            
        if os.getenv("user") and os.getenv("password") and os.getenv("host"):
             print("   ✅ Database credentials present.")
        else:
             print("   ❌ Database credentials MISSING.")
             errors.append("Config: Database credentials missing")

    except Exception as e:
        print(f"   ❌ CONFIG FAILED: {e}")
        errors.append(f"Config: {e}")

    print("\n--- AUDIT SUMMARY ---")
    if not errors:
        print("🏆 ALL SYSTEMS GO. PRODUCTION READY.")
    else:
        print(f"🛑 FOUND {len(errors)} ERRORS. FIX BEFORE PROD.")
        for err in errors:
            print(f"   - {err}")

if __name__ == "__main__":
    asyncio.run(run_audit())
