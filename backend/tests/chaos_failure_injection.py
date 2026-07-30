import asyncio
import logging
from unittest.mock import patch, MagicMock, AsyncMock
from api.v3.search import unified_nexus_search
from core.auth.integrity import verify_result_integrity

# Configure Logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chaos-tester")

class MockFingerprint:
    def __init__(self):
        self.fingerprint_hash = "chaos_device_hash_999"
        self.risk_score = 0.5
        self.user_id = None

async def run_redis_failure_test():
    """
    [CHAOS TEST] Simulates a total Redis outage.
    Verifies that the Search API degrades gracefully (Fail-Open) rather than 500ing.
    """
    logger.info("\n🧪 [CHAOS] Starting Redis Failure Injection (Logic-Bridge)...")
    
    mock_request = MagicMock()
    mock_request.headers = {"user-agent": "chaos-bot"}
    mock_request.client.host = "192.168.1.1"
    
    # Simulate Redis Outage and other dependencies
    with patch("services.identity_service.IdentityService") as mock_id_svc, \
         patch("core.nexus.search.interceptor.nexus_interceptor.intercept") as mock_intercept, \
         patch("core.nexus.search.gate.nexus_latency_gate.get_cached_search") as mock_cache:
        
        # Identity Service should still work (it uses DB + Redis, we mock it to succeed)
        mock_id_instance = mock_id_svc.return_value
        mock_id_instance.get_or_create_fingerprint = AsyncMock(return_value=MockFingerprint())
        
        # [CHAOS] Force Interceptor to fail due to "Redis Connection Error"
        from redis.exceptions import ConnectionError
        mock_intercept.side_effect = ConnectionError("Redis cluster unreachable")
        
        # [CHAOS] Force Cache to fail
        mock_cache.side_effect = ConnectionError("L2 Cache Down")
        
        try:
            # The orchestrator should catch these errors and Fall-Open to the primary engine
            # We mock the primary engine (search_routes) to return a success
            with patch("services.search_service.SearchService.search_routes") as mock_engine:
                mock_engine.return_value = {"status": "SUCCESS", "data": {"journeys": [{"id": "fallback_1"}]}}
                
                response = await unified_nexus_search(
                    request=mock_request,
                    background_tasks=MagicMock(),
                    source="NDLS",
                    destination="BCT",
                    date="2026-04-25",
                    persona="ECONOMY",
                    tier="BASIC",
                    budget=None,
                    bypass_cache=False,
                    engine_model="TURBO",
                    db=MagicMock()
                )
                
                if response["status"] == "SUCCESS":
                    logger.info("✅ [CHAOS] Success: API survived Redis outage via Fail-Open logic.")
                else:
                    logger.error(f"❌ [CHAOS] Failure: API returned {response['status']} during Redis outage.")
        except Exception as e:
            import traceback
            logger.error(f"❌ [CHAOS] CRITICAL: API Crashed during Redis outage: {e}")
            logger.error(traceback.format_exc())

async def run_integrity_tamper_test():
    """
    [CHAOS TEST] Simulates a Signature Tamper attempt.
    Verifies that the integrity layer correctly blocks modified data.
    """
    logger.info("\n🧪 [CHAOS] Starting Signature Tamper Injection...")
    
    payload = {"journeys": [{"train": "123", "fare": 500}]}
    user_id = "test_user"
    nonce = "abcd123"
    ts = 1713770000
    
    # 1. Generate valid signature
    from core.auth.integrity import sign_result_payload
    valid_sig = sign_result_payload(payload, user_id, nonce, ts)
    
    # 2. Tamper with payload
    tampered_payload = {"journeys": [{"train": "123", "fare": 1}]} # Fare changed!
    
    # 3. Verify
    is_valid = verify_result_integrity(tampered_payload, valid_sig, user_id, nonce, ts)
    
    if not is_valid:
        logger.info("✅ [CHAOS] Success: Integrity layer detected and blocked the tampered fare.")
    else:
        logger.error("❌ [CHAOS] Failure: Integrity layer allowed a tampered payload!")

async def main():
    await run_redis_failure_test()
    await run_integrity_tamper_test()

if __name__ == "__main__":
    asyncio.run(main())
