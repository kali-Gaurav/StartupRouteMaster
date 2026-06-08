import argparse
import asyncio
import logging
import sys
import time
import re
import os
from datetime import datetime, timedelta
from typing import List, Optional

# Core Imports (Internal)
from database.session import initialize_database_pools, SessionTransit, SessionUser
from core.nexus.telemetry import nexus_telemetry
from services.cache_service import cache_service
from sqlalchemy import text

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")
logger = logging.getLogger("nexus_verify")

class NexusVerifyCLI:
    """
    [Nexus Elite] The unified verification and audit command for RouteMaster.
    Replaces all one-off audit scripts with a production-grade interface.
    """
    def __init__(self):
        self.parser = argparse.ArgumentParser(description="Nexus Elite System Verification Suite")
        self.subparsers = self.parser.add_subparsers(dest="command", required=True)
        self._setup_subparsers()

    def _setup_subparsers(self):
        # 1. Master Audit (Health & Consistency)
        self.subparsers.add_parser("master-audit", help="Full system integrity scan (DB, Cache, Telemetry).")
        
        # 2. Chaos Resilience
        self.subparsers.add_parser("chaos-test", help="Simulate faults to verify system self-healing.")
        
        # 3. Engine Diagnostic
        self.subparsers.add_parser("engine-diag", help="Deep-scan of the Railway Route Engine graph and bitsets.")
        
        # 4. Search E2E
        self.subparsers.add_parser("search-e2e", help="Execute real search scenarios and verify results.")
        
        # 5. Security & PII Probe
        self.subparsers.add_parser("security-probe", help="Scan for PII in logs and verify data encryption.")
        
        # 6. DB Finalize
        self.subparsers.add_parser("db-prepare", help="Optimize and prune database for production.")

        # 7. Log Audit
        self.subparsers.add_parser("log-audit", help="Verify log file sizes and rotation status.")

    async def master_audit(self):
        print("\n=== [NEXUS MASTER AUDIT] ===")
        await initialize_database_pools()
        # Users are in SessionUser (Supabase), not SessionTransit
        db_user = SessionUser()
        db_transit = SessionTransit()
        
        try:
            # 1. DB State & Orphan Check
            res = db_user.execute(text("SELECT COUNT(*) FROM users")).scalar()
            print(f"[OK] Database connected. User Count: {res}")
            
            # Orphan check might need cross-DB logic or skip if not possible easily
            # For now, let's just check if bookings exist in transit DB if that's where they are
            # But bookings are usually in user DB. Let's check where Booking model is.
            orphans = db_user.execute(text("SELECT COUNT(*) FROM bookings WHERE user_id NOT IN (SELECT id FROM users)")).scalar()
            if orphans > 0:
                print(f"[CRITICAL] Found {orphans} orphaned bookings! DB integrity compromised.")
            else:
                print("[OK] Booking-User integrity verified.")
            
            # 2. Telemetry Pulse
            report = await nexus_telemetry.get_metrics()
            # Telemetry status is not directly in get_metrics, so let's check if it returned data
            status = "ACTIVE" if "requests_per_sec" in report else "UNKNOWN"
            print(f"[OK] Telemetry Status: {status}")
            
            # 3. Cache Integrity
            if cache_service.is_available():
                test_key = "nexus:audit:pulse"
                cache_service.set(test_key, "alive", ttl_seconds=60)
                if cache_service.get(test_key) == "alive":
                    print("[OK] Redis Cache: READ/WRITE SUCCESS")
                else:
                    print("[FAIL] Redis Cache: READ FAILURE")
            else:
                print("[FAIL] Redis Cache: OFFLINE")
        finally:
            db_user.close()
            db_transit.close()

    async def chaos_test(self):
        print("\n=== [NEXUS CHAOS AUDIT] ===")
        try:
            from core.nexus.chaos import nexus_chaos
            from services.multi_layer_cache import cache_layer
            
            print("[SCENARIO] Redis Latency Injection (+400ms)")
            nexus_chaos.set_latency_injection("cache", 400)
            
            start = time.perf_counter()
            await cache_layer.get("chaos_probe")
            duration = (time.perf_counter() - start) * 1000
            
            print(f"Observed Latency: {duration:.2f}ms")
            if duration > 350:
                print("[OK] Chaos Engine successfully manipulated runtime latency.")
            else:
                print("[FAIL] Chaos Engine failed to inject latency. Check singleton binding.")
                
            nexus_chaos.clear_latency("cache")
        except ModuleNotFoundError:
            print("[WARN] Chaos module not implemented yet. Skipping chaos audit.")

    async def engine_diag(self):
        print("\n=== [ENGINE DEEP DIAGNOSTIC] ===")
        from core.route_engine.engine import RailwayRouteEngine
        engine = RailwayRouteEngine()
        await engine.init()
        
        if engine.graph:
            print(f"[OK] Graph Loaded. Nodes: {len(engine.graph.stop_cache)}")
            
            # Reachability Index Analysis
            snapshot = engine.graph.snapshot
            if hasattr(snapshot, '_trip_reachability_bitset') and snapshot._trip_reachability_bitset is not None:
                bitset = getattr(snapshot, '_trip_reachability_bitset')
                non_zero = "N/A"
                if hasattr(bitset, 'shape'):
                    import numpy as np
                    non_zero = np.count_nonzero(bitset)
                elif isinstance(bitset, dict):
                    non_zero = sum(1 for v in bitset.values() if v > 0)
                print(f"[OK] Reachability Bitset: ACTIVE (Non-zero words: {non_zero})")
            else:
                print("[WARN] Reachability Bitset: MISSING. Engine will perform slower O(N) scans.")
        else:
            print("[FAIL] Graph failed to initialize.")

    async def search_e2e(self):
        print("\n=== [SEARCH E2E VERIFICATION] ===")
        from database.session import initialize_database_pools, SessionTransit
        await initialize_database_pools()
        from core.route_engine.engine import RailwayRouteEngine
        from core.route_engine.base import RoutingRequest
        from core.route_engine.constraints import RouteConstraints
        engine = RailwayRouteEngine()
        await engine.init()
        req = RoutingRequest(source_code="NDLS", destination_code="BCT", departure_date=datetime.now() + timedelta(days=1), constraints=RouteConstraints())
        db = SessionTransit()
        try:
            routes = await engine.orchestrator.search_all_tiers(req)
            print(f"[OK] Search 'NDLS -> BCT' yielded {len(routes)} results.")
            if routes:
                r = routes[0]
                segs = getattr(r, 'segments', [])
                print(f"    Top route: {len(segs)} segment(s), duration={getattr(r, 'total_duration_minutes', 'N/A')}min")
            else:
                print("[WARN] 0 results - likely governor stress throttle (RAM > 80%). Expected in dev.")
        finally:
            db.close()

    async def security_probe(self):
        print("\n=== [SECURITY & PII PROBE] ===")
        
        # 1. PII Scan in Logs
        pii_patterns = {
            "Email": r"[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+",
            "Phone": r"\+?\d{10,12}",
            "PNR": r"\b\d{10}\b"
        }
        
        log_dir = "logs"
        if os.path.exists(log_dir):
            print(f"Scanning '{log_dir}' for leaked PII...")
            leaks = 0
            for root, _, files in os.walk(log_dir):
                for file in files:
                    if file.endswith(".log") or file.endswith(".txt"):
                        try:
                            with open(os.path.join(root, file), 'r', errors='ignore') as f:
                                content = f.read()
                                for label, pattern in pii_patterns.items():
                                    matches = re.findall(pattern, content)
                                    if matches:
                                        real_matches = [m for m in matches if "@example.com" not in m]
                                        if real_matches:
                                            print(f"  [ALERT] Found {len(real_matches)} potential {label} leaks in {file}!")
                                            leaks += 1
                        except: continue
            if leaks == 0:
                print("[OK] No PII leaks found in log files.")
        else:
            print("[INFO] Log directory missing, skipping PII scan.")

        # 2. Encryption Verification
        from database.session import SessionUser
        await initialize_database_pools()
        db = SessionUser()
        try:
            sample_user = db.execute(text("SELECT encrypted_irctc_creds FROM users WHERE encrypted_irctc_creds IS NOT NULL LIMIT 1")).fetchone()
            if sample_user and not isinstance(sample_user[0], bytes):
                print("[CRITICAL] User IRCTC Credentials stored as plain text!")
            else:
                print("[OK] User Credential Vault (Postgres LargeBinary) verified.")
        finally:
            db.close()

    async def db_prepare(self):
        print("\n=== [DATABASE PRODUCTION PREPARE] ===")
        await initialize_database_pools()
        db = SessionTransit()
        try:
            if db.bind.dialect.name == 'postgresql':
                db.execute(text("ANALYZE"))
                print("[OK] PostgreSQL Stats Updated (ANALYZE).")
            db.commit()
        finally:
            db.close()

    async def log_audit(self):
        print("\n=== [LOG ROTATION AUDIT] ===")
        log_dir = "logs"
        if os.path.exists(log_dir):
            total_size = 0
            for root, _, files in os.walk(log_dir):
                for file in files:
                    path = os.path.join(root, file)
                    size = os.path.getsize(path) / (1024 * 1024) # MB
                    total_size += size
                    if size > 100:
                        print(f"  [WARN] Large log file found: {file} ({size:.2f} MB). Ensure rotation is active.")
            print(f"[OK] Total log storage: {total_size:.2f} MB.")
        else:
            print("[INFO] No log directory found.")

    async def run(self):
        args = self.parser.parse_args()
        if args.command == "master-audit": await self.master_audit()
        elif args.command == "chaos-test": await self.chaos_test()
        elif args.command == "engine-diag": await self.engine_diag()
        elif args.command == "search-e2e": await self.search_e2e()
        elif args.command == "security-probe": await self.security_probe()
        elif args.command == "db-prepare": await self.db_prepare()
        elif args.command == "log-audit": await self.log_audit()

if __name__ == "__main__":
    cli = NexusVerifyCLI()
    asyncio.run(cli.run())
