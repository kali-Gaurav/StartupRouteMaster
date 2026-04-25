import asyncio
import pytest
import uuid
import time
from unittest.mock import patch, MagicMock
from api.v3.search import unified_nexus_search
from core.auth.integrity import verify_result_integrity

# Mocking for Direct Logic Testing
class MockFingerprint:
    def __init__(self):
        self.fingerprint_hash = "test_device_hash_12345"
        self.risk_score = 0.1
        self.user_id = None

@pytest.mark.asyncio
async def test_joint_logic_masking_and_signing():
    """
    [STABILITY PASS] Joint 1: Sequence Validation (Direct Logic).
    Verifies that the signature is valid FOR THE MASKED PAYLOAD.
    """
    # 1. Setup Mock Request and DB
    mock_request = MagicMock()
    mock_request.headers = {"user-agent": "pytest-rigor-v3"}
    mock_request.client.host = "127.0.0.1"
    mock_db = MagicMock()
    
    # 2. Patch internal service dependencies
    with patch("services.identity_service.IdentityService") as mock_id_svc, \
         patch("core.nexus.search.interceptor.nexus_interceptor.intercept", new_callable=MagicMock) as mock_intercept, \
         patch("core.nexus.search.gate.nexus_latency_gate.get_cached_search", new_callable=MagicMock) as mock_cache:
        
        # Setup Identity Mock as AsyncMock
        mock_id_instance = mock_id_svc.return_value
        mock_id_instance.get_or_create_fingerprint = MagicMock(side_effect=lambda *args, **kwargs: asyncio.sleep(0, result=MockFingerprint()))
        # Actually, let's use a simpler way for AsyncMock in pytest-asyncio
        from unittest.mock import AsyncMock
        mock_id_instance.get_or_create_fingerprint = AsyncMock(return_value=MockFingerprint())
        
        # Setup Interceptor Mock (Allow Search)
        mock_intercept.return_value = AsyncMock(return_value=MagicMock(allowed=True, metadata={}))()
        # Wait, let's just use AsyncMock directly
        mock_intercept.side_effect = AsyncMock(return_value=MagicMock(allowed=True, metadata={}))
        
        # Setup Cache Mock
        mock_cache.side_effect = AsyncMock(return_value=[{
            "train_number": "12431",
            "fare": 500.0,
            "guardian_score": 9.5,
            "comfort_rank": 1
        }])
        
        # 3. Call the Orchestrator Directly
        # We must provide explicit strings for all Query parameters to avoid 'AttributeError' on Query objects
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
            db=mock_db
        )
        
        # 4. Verification
        assert response["status"] == "SUCCESS"
        payload = response["data"]
        signature = response["integrity_sig"]
        nonce = response["metadata"]["nonce"]
        fingerprint_hash = response["metadata"]["fingerprint"]
        
        # Check Masking
        for journey in payload["journeys"]:
            assert "guardian_score" not in journey, "FAIL: Premium field 'guardian_score' leaked to BASIC tier"
            assert "comfort_rank" not in journey, "FAIL: Premium field 'comfort_rank' leaked to BASIC tier"
            
        # Check Integrity Signing (Contextual Integrity 2.0)
        # Note: user_id fallback is fingerprint_hash in our code
        ts = response["metadata"]["ts"]
        is_valid = verify_result_integrity(payload, signature, user_id=fingerprint_hash, nonce=nonce, ts=ts)
        assert is_valid, "FAIL: Signature invalid! Likely signed before masking or with wrong context."
        print("\n✅ [STABILITY] Joint 1 (Mask->Sign) Verified.")

if __name__ == "__main__":
    import pytest
    asyncio.run(pytest.main([__file__]))
