import asyncio
import os
import aiohttp
import logging
import json
import time
from sqlalchemy import text
from dotenv import load_dotenv

# Add current directory to path so database module can be found
import sys
from pathlib import Path
sys.path.append(str(Path(__file__).resolve().parent.parent))

# Load configuration
load_dotenv('backend/.env')

logging.basicConfig(level=logging.INFO, format='%(levelname)s: %(message)s')
logger = logging.getLogger("SystemIntegrity")

async def test_primary_database():
    print("🔍 Testing Primary Database (via SessionLocal)...")
    from database.session import SessionLocal
    try:
        db = SessionLocal()
        start = time.time()
        res = db.execute(text("SELECT NOW()")).scalar()
        latency = (time.time() - start) * 1000
        print(f"   ✅ Database Connected! Latency: {latency:.2f}ms | Server time: {res}")
        
        # Comprehensive Data Check
        trips = db.execute(text("SELECT count(*) FROM trips")).scalar()
        stops = db.execute(text("SELECT count(*) FROM stops")).scalar()
        segments = db.execute(text("SELECT count(*) FROM segments")).scalar()
        
        print(f"   📊 Data Summary:")
        print(f"      -> Trips: {trips}")
        print(f"      -> Stops: {stops}")
        print(f"      -> Segments: {segments}")
        
        db.close()
        return True
    except Exception as e:
        print(f"   ❌ Primary Database Connection Failed: {e}")
        return False

async def test_redis(url):
    print("🔍 Testing Redis (Upstash) Connection...")
    if not url:
        print("   ⚠️ REDIS_URL not set in environment.")
        return False
    try:
        import redis
        r = redis.from_url(url, decode_responses=True, ssl_cert_reqs=None)
        start = time.time()
        r.set("integrity_ping", "pong")
        val = r.get("integrity_ping")
        latency = (time.time() - start) * 1000
        if val == "pong":
            print(f"   ✅ Redis Connected! Latency: {latency:.2f}ms")
            return True
        else:
            print("   ❌ Redis returned incorrect value.")
            return False
    except Exception as e:
        print(f"   ❌ Redis Connection Failed: {e}")
        return False

async def test_supabase_api(url, key):
    print("🔍 Testing Supabase API Heartbeat...")
    if not url or not key:
        print("   ⚠️ SUPABASE_URL or SUPABASE_KEY not set.")
        return False
    try:
        headers = {"apikey": key, "Authorization": f"Bearer {key}"}
        async with aiohttp.ClientSession() as session:
            async with session.get(f"{url}/rest/v1/", headers=headers) as resp:
                if resp.status == 200:
                    print(f"   ✅ Supabase API OK (HTTP {resp.status})")
                    return True
                else:
                    print(f"   ❌ Supabase API Failed (HTTP {resp.status})")
                    return False
    except Exception as e:
        print(f"   ❌ Supabase API Error: {e}")
        return False

async def test_rapid_api(key):
    print("🔍 Testing RapidAPI (IRCTC & Live Status) Heartbeat...")
    if not key:
        print("   ⚠️ RAPIDAPI_KEY not set.")
        return False
    
    headers = {"X-RapidAPI-Key": key, "X-RapidAPI-Host": "irctc1.p.rapidapi.com"}
    async with aiohttp.ClientSession(timeout=aiohttp.ClientTimeout(total=60)) as session:
        # 1. IRCTC Check
        for attempt in range(3):
            try:
                async with session.get("https://irctc1.p.rapidapi.com/api/v1/searchTrain?query=12002", headers=headers) as resp:
                    if resp.status == 200:
                        print(f"   ✅ RapidAPI IRCTC OK (HTTP 200)")
                        break
                    elif resp.status == 504:
                        print(f"   ⚠️ RapidAPI IRCTC Timeout (504), retrying {attempt+1}/3...")
                        await asyncio.sleep(2)
                    else:
                        print(f"   ❌ RapidAPI IRCTC Failed (HTTP {resp.status})")
                        break
            except Exception as e:
                print(f"   ❌ RapidAPI IRCTC Error: {e}")
                break

        # 2. Live Status Check (Rappid.in)
        live_url = os.getenv("LIVE_STATUS_BASE_URL", "https://rappid.in/apis/train.php")
        try:
            async with session.get(f"{live_url}?train_no=12002") as resp:
                if resp.status == 200:
                    data = await resp.json()
                    if data.get("success"):
                        print(f"   ✅ Rappid.in Live Status OK")
                    else:
                        print(f"   ⚠️ Rappid.in responded but success=False: {data.get('message')}")
                else:
                    print(f"   ❌ Rappid.in Failed (HTTP {resp.status})")
        except Exception as e:
            print(f"   ❌ Rappid.in Error: {e}")

async def run_full_verify():
    print(f"\n{'='*60}")
    print(f"🚀 FINAL SYSTEM INTEGRATION & CONNECTION CHECK")
    print(f"{'='*60}\n")
    
    # 1. Primary Master Database
    await test_primary_database()
    
    # 2. Redis
    await test_redis(os.getenv("REDIS_URL"))
    
    # 3. Supabase API
    await test_supabase_api(os.getenv("SUPABASE_URL"), os.getenv("SUPABASE_KEY"))
    
    # 4. External APIs
    await test_rapid_api(os.getenv("RAPIDAPI_KEY"))
    
    print(f"\n{'='*60}")
    print(f"🏁 INTEGRATION CHECK COMPLETE")
    print(f"{'='*60}\n")

if __name__ == "__main__":
    asyncio.run(run_full_verify())
