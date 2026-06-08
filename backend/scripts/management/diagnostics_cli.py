import argparse
import asyncio
import os
import sys
from dotenv import load_dotenv

def main():
    parser = argparse.ArgumentParser(description="RouteMaster Diagnostics & Utility CLI")
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Subcommand: env
    env_parser = subparsers.add_parser("env", help="[READ-ONLY] Check required environment variables.")
    
    # Subcommand: db
    db_parser = subparsers.add_parser("db", help="[READ-ONLY] Probe SQLite database tables and schema.")
    
    # Subcommand: stations
    stat_parser = subparsers.add_parser("stations", help="[READ-ONLY] Check station availability.")
    stat_parser.add_argument("codes", nargs="*", help="Station codes to check (e.g., NDLS HWH).")

    # Subcommand: clear-cache
    cache_parser = subparsers.add_parser("clear-cache", help="[MUTATES] Clear station resolution caches in Redis.")
    
    # Subcommand: diagnose-tbr
    tbr_parser = subparsers.add_parser("diagnose-tbr", help="[READ-ONLY] Diagnose Trip-Based Router reachability.")
    tbr_parser.add_argument("source", help="Source station code (e.g., NDLS)")
    tbr_parser.add_argument("dest", help="Destination station code (e.g., HWH)")

    # Subcommand: diagnose-guardian
    g_parser = subparsers.add_parser("diagnose-guardian", help="[READ-ONLY] Diagnose Guardian AI Memory and Safety Loop.")

    args = parser.parse_args()

    load_dotenv()

    if args.command == "env":
        check_env()
    elif args.command == "db":
        asyncio.run(probe_db())
    elif args.command == "stations":
        asyncio.run(check_stations(args.codes))
    elif args.command == "clear-cache":
        asyncio.run(clear_cache())
    elif args.command == "diagnose-tbr":
        asyncio.run(diagnose_tbr(args.source, args.dest))
    elif args.command == "diagnose-guardian":
        asyncio.run(diagnose_guardian())

def check_env():
    print("--- Environment Check ---")
    vars_to_check = {
        "SUPABASE_URL": "Supabase URL",
        "SUPABASE_SERVICE_ROLE_KEY": "Supabase Key",
        "REDIS_URL": "Redis URL",
        "CLOUDFLARE_R2_ACCOUNT_ID": "R2 Account ID",
        "CLOUDFLARE_R2_S3_API": "R2 S3 API",
        "CLOUDFLARE_R2_ACCESS_KEY_ID": "R2 Key ID"
    }
    for env_var, name in vars_to_check.items():
        val = os.getenv(env_var)
        if not val:
            print(f"[FAIL] {name} ({env_var}) is NOT SET.")
        else:
            print(f"[OK] {name} ({env_var}) is SET.")
            if env_var == "REDIS_URL":
                if "@" not in val and ":" in val[9:]:
                     print("  [WARN] REDIS_URL seems to lack authentication credentials.")
                if "upstash.io" in val and not val.startswith("rediss://"):
                     print("  [WARN] REDIS_URL for Upstash should start with rediss:// (SSL).")

async def probe_db():
    print("--- Database Probe ---")
    from database.session import SessionTransit, initialize_database_pools
    from sqlalchemy import text
    await initialize_database_pools()
    s = SessionTransit()
    
    # Tables
    if s.bind.dialect.name == 'sqlite':
        res = s.execute(text("SELECT name FROM sqlite_master WHERE type='table'")).fetchall()
    else:
        res = s.execute(text("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")).fetchall()
    print("Found Tables:")
    for r in res:
        print(f"  - {r[0]}")
        
    # Check calendar boundaries
    cal = s.execute(text("SELECT MIN(start_date), MAX(end_date) FROM calendar")).fetchone()
    if cal and cal[0]:
        print(f"Active Service Schedule Range: {cal[0]} to {cal[1]}")
    s.close()

async def check_stations(codes):
    print("--- Station Check ---")
    from database.session import SessionTransit, initialize_database_pools
    from database.models import Stop
    from sqlalchemy import text
    await initialize_database_pools()
    db = SessionTransit()
    if not codes:
        print("Listing sample of 20 stations:")
        res = db.execute(text("SELECT id, code, name FROM stops LIMIT 20")).fetchall()
        for r in res:
            print(f"{r[0]:6} | {r[1]:8} | {r[2]}")
    else:
        for code in codes:
            s = db.query(Stop).filter(Stop.code == code.upper()).first()
            if s:
                print(f"[OK] {code.upper()}: ID={s.id}, Name={s.name}")
            else:
                print(f"[FAIL] {code.upper()}: NOT FOUND")
    db.close()

async def clear_cache():
    print("--- Clear Station Cache [MUTATES] ---")
    from services.cache_service import cache_service
    from typing import cast, List
    if not cache_service.is_available() or cache_service.redis is None:
        print("[FAIL] Redis not available.")
        return
    redis_client = cache_service.redis
    keys = cast(List[str], redis_client.keys("v1:station_resolve:*"))
    print(f"Clearing {len(keys)} cached station resolution keys...")
    for key in keys:
        if isinstance(key, bytes):
            key = key.decode("utf-8")
        clean_key = key.replace("v1:", "")
        cache_service.delete(clean_key)
    print("[OK] Done.")

async def diagnose_tbr(src_code, dst_code):
    print(f"--- TBR Diagnosis: {src_code} -> {dst_code} ---")
    from datetime import datetime, timedelta
    from core.route_engine.tbr_router import TripBasedRouter
    from database.session import initialize_database_pools
    
    await initialize_database_pools()
    tbr = TripBasedRouter()
    date = datetime.now() + timedelta(days=2)
    graph = await tbr.get_graph(date)
    
    if graph is None:
        print("[FAIL] ERROR: Graph unavailable")
        return

    src_stop = graph.get_stop_by_code(src_code)
    dst_stop = graph.get_stop_by_code(dst_code)
    
    if not src_stop or not dst_stop:
        print("[FAIL] ERROR: Could not find one or both stops")
        return

    print(f"[INFO] Source ID: {src_stop.id}, Dest ID: {dst_stop.id}")
    
    if tbr._edges is None:
        print("[FAIL] ERROR: _edges is None")
    else:
        print(f"[OK] Edges loaded: {len(tbr._edges)}")
        
    deps = graph.get_departures_from_stop(src_stop.id, date, 1440)
    print(f"[TRAIN] Departures from source: {len(deps)}")
    if deps:
        tid = deps[0][1]
        can_reach = graph.can_reach_destination(tid, dst_stop.id)
        print(f"Sample Trip {tid} can reach dest bitset: {can_reach}")
        seq = graph.get_stop_sequence_in_trip(tid, src_stop.id)
        print(f"Sample Trip {tid} sequence: {seq}")

async def diagnose_guardian():
    print("--- Guardian AI Diagnostics ---")
    try:
        from guardian_ai.memory_store import guardian_memory
        
        # Test Cache Connection
        if guardian_memory.cache.is_available():
            print("[OK] Guardian Memory (Redis) is reachable.")
        else:
            print("[FAIL] Guardian Memory (Redis) is disconnected. AI is in degraded mode.")
            return

        active_missions = await guardian_memory.get_all_active_missions()
        print(f"Active Missions Tracked: {len(active_missions)}")
        
        for m in active_missions:
            print(f"  - Mission: {m.mission_id} | User: {m.user_id} | Risk: {m.risk_level.name} ({m.risk_score})")
            
    except ImportError as e:
        print(f"[FAIL] Guardian AI module missing or broken: {e}")
    except Exception as e:
        print(f"[FAIL] Error running diagnostics: {e}")

if __name__ == "__main__":
    main()
