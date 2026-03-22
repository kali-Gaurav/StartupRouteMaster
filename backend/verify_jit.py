import os
import sys
import asyncio
import logging

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

async def test_hardened_jit():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger("verify-jit")
    
    logger.info("🔍 START: Verifying Hardened JIT Manager...")
    
    try:
        from services.jit_manager import jit_manager, JITState
        
        # Test Case 1: Successful load
        logger.info("--- Test Case 1: Basic Success ---")
        async def slow_loader():
            logger.info("Executing slow_loader...")
            await asyncio.sleep(0.1)
            
        jit_manager.register_node("TEST_OK", [], slow_loader, retries=1)
        await jit_manager.ensure_ready("TEST_OK")
        status = jit_manager.get_status()
        if status["nodes"]["TEST_OK"]["state"] == "ready":
            logger.info("✅ TEST_OK loaded successfully.")
        
        # Test Case 2: Timeout
        logger.info("--- Test Case 2: Timeout ---")
        async def hanging_loader():
            logger.info("Executing hanging_loader (should timeout)...")
            await asyncio.sleep(5)
            
        jit_manager.register_node("TEST_TIMEOUT", [], hanging_loader, timeout=0.1, retries=0)
        try:
            await jit_manager.ensure_ready("TEST_TIMEOUT")
            logger.error("❌ TEST_TIMEOUT should have failed.")
        except (TimeoutError, asyncio.TimeoutError):
            logger.info("✅ TEST_TIMEOUT failed as expected.")
        except Exception as e:
            logger.info(f"✅ TEST_TIMEOUT caught exception of type {type(e).__name__}: {e}")
            
        # Test Case 3: Retry mechanism
        logger.info("--- Test Case 3: Retry ---")
        fail_count = 0
        async def flaky_loader():
            nonlocal fail_count
            fail_count += 1
            if fail_count < 2:
                logger.info(f"Flaky attempt {fail_count} failing...")
                raise ValueError("Transient error")
            logger.info("Flaky attempt 2 succeeding...")
            
        jit_manager.register_node("TEST_RETRY", [], flaky_loader, retries=2)
        await jit_manager.ensure_ready("TEST_RETRY")
        status = jit_manager.get_status()
        if status["nodes"]["TEST_RETRY"]["state"] == "ready" and status["nodes"]["TEST_RETRY"]["retries"] == 1:
            logger.info("✅ TEST_RETRY succeeded after 1 retry.")
        else:
            logger.error(f"❌ TEST_RETRY status: {status['nodes']['TEST_RETRY']}")

        logger.info("✨ END: JIT verification complete.")
        
    except Exception as e:
        logger.error(f"❌ JIT verification failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    try:
        asyncio.run(asyncio.wait_for(test_hardened_jit(), timeout=15))
    except asyncio.TimeoutError:
        print("❌ Script timed out after 15s")
        sys.exit(1)
