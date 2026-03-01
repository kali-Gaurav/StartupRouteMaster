import asyncio
import os
import sys
import logging
import json
from datetime import datetime

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger("diagnostics")

# Add backend to path
sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.getcwd(), 'backend', '.env'))

async def check_supabase():
    print("\n--- [1/5] Checking Supabase Auth & DB ---")
    try:
        from supabase_client import supabase
        # Test basic query
        start = datetime.now()
        response = supabase.from_("profiles").select("id").limit(1).execute()
        duration = (datetime.now() - start).total_seconds() * 1000
        
        print(f"✅ Supabase Connection: SUCCESS ({duration:.2f}ms)")
        # Check if we got data or a valid response object
        if hasattr(response, 'data'):
            print(f"✅ Supabase Data Access: SUCCESS (Found {len(response.data)} records)")
        return True
    except Exception as e:
        print(f"❌ Supabase Connection: FAILED - {e}")
        return False

async def check_redis():
    print("\n--- [2/5] Checking Upstash Redis ---")
    try:
        from core.redis import async_redis_client
        start = datetime.now()
        pong = await async_redis_client.ping()
        duration = (datetime.now() - start).total_seconds() * 1000
        
        if pong:
            print(f"✅ Redis Ping: SUCCESS ({duration:.2f}ms)")
            # Test a set/get
            await async_redis_client.set("diag_test", "ok", ex=10)
            val = await async_redis_client.get("diag_test")
            if val == "ok":
                print("✅ Redis Read/Write: SUCCESS")
            return True
        else:
            print("❌ Redis Ping: FAILED (Empty response)")
            return False
    except Exception as e:
        print(f"❌ Redis Connection: FAILED - {e}")
        return False

async def check_railway_db():
    print("\n--- [3/5] Checking Railway PostgreSQL ---")
    try:
        from database.session import SessionLocal
        from sqlalchemy import text
        
        db = SessionLocal()
        start = datetime.now()
        result = db.execute(text("SELECT 1")).fetchone()
        duration = (datetime.now() - start).total_seconds() * 1000
        
        if result[0] == 1:
            print(f"✅ Railway DB Connection: SUCCESS ({duration:.2f}ms)")
            
            # Check table existence
            table_count = db.execute(text("SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'")).scalar()
            print(f"✅ Railway DB Schema: SUCCESS ({table_count} tables found)")
            
            db.close()
            return True
        return False
    except Exception as e:
        print(f"❌ Railway DB Connection: FAILED - {e}")
        return False

async def check_rapid_irctc():
    print("\n--- [4/5] Checking RapidAPI (IRCTC1) ---")
    api_key = os.getenv("RAPID_API_KEY") or os.getenv("RAPIDAPI_KEY")
    if not api_key:
        print("⚠️ RapidAPI Key missing in .env")
        return False
        
    try:
        import httpx
        headers = {
            "X-RapidAPI-Key": api_key,
            "X-RapidAPI-Host": "irctc1.p.rapidapi.com"
        }
        url = "https://irctc1.p.rapidapi.com/api/v1/getTrainSchedule"
        params = {"trainNo": "12951"}
        
        async with httpx.AsyncClient(timeout=10.0) as client:
            start = datetime.now()
            resp = await client.get(url, headers=headers, params=params)
            duration = (datetime.now() - start).total_seconds() * 1000
            
            if resp.status_code == 200:
                print(f"✅ RapidAPI IRCTC: SUCCESS ({duration:.2f}ms)")
                return True
            else:
                print(f"❌ RapidAPI IRCTC: FAILED (Status {resp.status_code})")
                print(f"DEBUG: {resp.text[:200]}")
                return False
    except Exception as e:
        print(f"❌ RapidAPI IRCTC: ERROR - {type(e).__name__}: {str(e)}")
        return False

async def check_rappid_url():
    print("\n--- [5/5] Checking Rappid.in (Live Status) ---")
    try:
        from services.realtime_ingestion.live_status_service import LiveStatusService
        svc = LiveStatusService()
        
        start = datetime.now()
        # Test with a high-profile train
        status = await svc.get_live_status("12951")
        duration = (datetime.now() - start).total_seconds() * 1000
        
        if status:
            print(f"✅ Rappid.in Live Status: SUCCESS ({duration:.2f}ms)")
            print(f"✅ Current position: {status.get('current_station_name')} (Delay: {status.get('delay_minutes')}m)")
            return True
        else:
            print("❌ Rappid.in Live Status: FAILED (No data returned)")
            return False
    except Exception as e:
        print(f"❌ Rappid.in Live Status: ERROR - {e}")
        return False

async def main():
    print("============================================================")
    print(f"   RouteMaster Production Diagnostics - {datetime.now()}")
    print("============================================================")
    
    # Run in sequence to avoid overloading shared resources/logs
    r1 = await check_supabase()
    r2 = await check_redis()
    r3 = await check_railway_db()
    r4 = await check_rapid_irctc()
    r5 = await check_rappid_url()
    
    results = [r1, r2, r3, r4, r5]
    
    print("\n============================================================")
    if all(results):
        print("🚀 ALL SYSTEMS OPERATIONAL - READY FOR PRODUCTION DEPLOYMENT")
    else:
        print("⚠️ SOME SYSTEMS DEGRADED - REVIEW ERRORS ABOVE")
    print("============================================================")

if __name__ == "__main__":
    asyncio.run(main())
