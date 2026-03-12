import asyncio
import httpx
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify-subtask-1.9")

BASE_URL = "http://127.0.0.1:8000"

async def test_request_id_propagation():
    logger.info("Testing Request ID propagation...")
    async with httpx.AsyncClient() as client:
        # 1. System generated ID
        resp = await client.get(f"{BASE_URL}/api/health")
        rid = resp.headers.get("X-Request-ID")
        logger.info(f"Received System RID: {rid}")
        assert rid is not None
        
        # 2. Client provided ID
        client_rid = "test-custom-rid-123"
        resp = await client.get(f"{BASE_URL}/api/health", headers={"X-Request-ID": client_rid})
        received_rid = resp.headers.get("X-Request-ID")
        logger.info(f"Received Client RID: {received_rid}")
        assert received_rid == client_rid

async def main():
    await test_request_id_propagation()
    logger.info("✅ Request ID Verification PASSED. Please check logs for matching [RID:...] entries.")

if __name__ == "__main__":
    asyncio.run(main())
