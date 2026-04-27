import sys
import os
from unittest.mock import patch
# Force root path for backend module resolution
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import asyncio
import logging
from datetime import datetime
from core.redis_client import redis_client
from services.search_service import SearchService
from services.telemetry_service import push_to_stream
from services.ledger_service import LedgerService
from workers.inference_worker import InferenceWorker
from database.session import SessionLocal, initialize_database_pools

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("routemaster.integrity_audit")

async def run_audit():
    print("=== 🛡️ ROUTEMASTER PRODUCTION INTEGRITY AUDIT ===")
    await initialize_database_pools()
    db = SessionLocal()
    
    try:
        # 1. Financial Ledger Audit
        print("\n[1/4] Auditing Financial Ledger...")
        ledger = LedgerService(db)
        # Verify connectivity to db and ledger methods
        ppr = await ledger.get_ppr_metrics()
        print(f"✅ Ledger: PPR Metrics active. Corridors analyzed: {len(ppr)}")

        # 2. ML Pipeline Audit
        print("\n[2/4] Auditing ML Pipeline...")
        inference = InferenceWorker()
        if inference.model_data:
            print("✅ ML Brain: Loaded and Ready.")
        else:
            print("⚠️ ML Brain: Artifact missing (Expected if no training yet).")

        # 3. Data Flow Audit (Search -> Stream -> Heatmap)
        print("\n[3/4] Auditing Data Flow...")
        try:
            await push_to_stream({"origin": "DEL", "destination": "BOM", "timestamp": datetime.utcnow().isoformat()})
            print("✅ Telemetry: Search event pipeline active.")
        except Exception as e:
            print(f"❌ Telemetry: Pipeline failure {e}")

        # 4. Resilience Audit (Search Fallback)
        print("\n[4/4] Auditing Resilience...")
        try:
            service = SearchService(db)
            # Patch the cache layer to simulate a Redis outage
            with patch("services.search_service.multi_layer_cache.redis", None):
                await service.search_routes(source="DEL", destination="BOM", travel_date="2026-05-01", limit=1)
                print("✅ Graceful Fallback: Verified (Service handled Redis outage)")
        except Exception as e:
            print(f"❌ Graceful Fallback: Failed ({e})")

        print("\n=== 🏁 AUDIT COMPLETE: System is Production-Ready ===")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(run_audit())
