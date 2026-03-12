import asyncio
import logging
import json
import os
import sys
from unittest.mock import AsyncMock, patch

# Ensure backend package is importable
sys.path.append(os.getcwd())

from backend.services.multi_layer_cache import MultiLayerCache
from backend.utils.compression import PayloadCompressor

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify-3.4")

async def test_payload_compression():
    cache_svc = MultiLayerCache()
    cache_svc.redis = AsyncMock()
    
    # 1. Test Compression Threshold
    logger.info("Testing small payload (should NOT be compressed)...")
    small_val = {"a": 1}
    await cache_svc.put("small_key", small_val)
    
    # Verify redis.setex was called with a string
    call_args = cache_svc.redis.setex.call_args[0]
    assert isinstance(call_args[2], str)
    logger.info("✅ Small payload remained uncompressed.")

    # 2. Test Large Payload Compression
    logger.info("Testing large payload (should be compressed)...")
    large_val = {"data": "x" * 2000} # Exceeds 1KB
    
    # Reset mock
    cache_svc.redis.setex.reset_mock()
    await cache_svc.put("large_key", large_val)
    
    # Verify redis.setex was called with bytes (compressed)
    call_args = cache_svc.redis.setex.call_args[0]
    assert isinstance(call_args[2], bytes)
    compressed_size = len(call_args[2])
    original_size = len(json.dumps(large_val))
    logger.info(f"✅ Large payload compressed: {original_size} -> {compressed_size} bytes.")
    assert compressed_size < original_size

    # 3. Test Decompression on Get
    logger.info("Testing decompression on get...")
    # Mock redis to return the compressed bytes
    compressed_payload, _ = PayloadCompressor.compress(large_val)
    # We must wrap it in the XFetch envelope as 'put' does
    import time
    xf_envelope = {"value": large_val, "xf_expiry": time.time()+100, "xf_delta": 0.1}
    compressed_envelope, _ = PayloadCompressor.compress(xf_envelope)
    
    cache_svc.redis.get.return_value = compressed_envelope
    cache_svc.lru.clear() # Force L2 check
    
    retrieved_val = await cache_svc.get("large_key")
    assert retrieved_val == large_val
    logger.info("✅ Decompression successful. Values match.")

if __name__ == "__main__":
    asyncio.run(test_payload_compression())
