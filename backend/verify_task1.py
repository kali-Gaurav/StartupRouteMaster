import os
import sys
import asyncio
import logging
from typing import Dict, Any

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

async def test_task1_middleware():
    logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
    logger = logging.getLogger("verify-task1")
    
    logger.info("🔍 Verifying Task 1 Refinements...")
    
    try:
        from core.middleware.engine import SmartMiddleware, PriorityLevel, SystemState
        from core.system_monitor import system_monitor
        
        # Mock ASGI App
        async def mock_app(scope, receive, send):
            await send({
                "type": "http.response.start",
                "status": 200,
                "headers": [(b"content-type", b"application/json")]
            })
            await send({
                "type": "http.response.body",
                "body": b'{"status": "ok"}'
            })

        middleware = SmartMiddleware(mock_app)
        
        async def call_middleware(path, method="GET"):
            scope = {
                "type": "http",
                "path": path,
                "method": method,
                "headers": []
            }
            results = []
            async def mock_send(message):
                results.append(message)
            
            await middleware(scope, None, mock_send)
            return results

        # 1. Test Essential Route (Always Allowed)
        logger.info("--- Testing Essential Route ---")
        await system_monitor.update_if_stale(force=True)
        # Manually force state to EMERGENCY for testing
        system_monitor._state = SystemState.EMERGENCY
        
        res = await call_middleware("/api/sos")
        headers = dict(res[0].get("headers", []))
        trace = headers.get(b"X-Middleware-Decision", b"").decode()
        logger.info(f"SOS Result (EMERGENCY): {res[0]['status']} | Trace: {trace}")
        if res[0]['status'] == 200:
             logger.info("✅ SOS endpoint allowed in EMERGENCY.")
        else:
             logger.error("❌ SOS endpoint BLOCKED in EMERGENCY.")

        # 2. Test Low Priority Route (Shed in WARNING/CRITICAL)
        logger.info("--- Testing Low Priority Route Shedding ---")
        system_monitor._state = SystemState.WARNING
        res = await call_middleware("/api/analytics")
        headers = dict(res[0].get("headers", []))
        trace = headers.get(b"X-Middleware-Decision", b"").decode()
        logger.info(f"Analytics Result (WARNING): {res[0]['status']} | Trace: {trace}")
        # In WARNING, LOW priority has multiplier 0.5 (Should be allowed if capacity not reached)
        # Wait, let's check the matrix: WARNING LOW is (0.5, 1.5). Shed=False.
        # CRITICAL LOW is (0.0, 2.0). Shed=True.
        
        system_monitor._state = SystemState.CRITICAL
        res = await call_middleware("/api/analytics")
        headers = dict(res[0].get("headers", []))
        trace = headers.get(b"X-Middleware-Decision", b"").decode()
        logger.info(f"Analytics Result (CRITICAL): {res[0]['status']} | Trace: {trace}")
        if res[0]['status'] == 503 and "shed_policy_CRITICAL" in trace:
             logger.info("✅ Analytics endpoint shed in CRITICAL as expected.")
        else:
             logger.error("❌ Analytics endpoint NOT shed in CRITICAL.")

        # 3. Test Trace Headers
        logger.info("--- Testing Trace Headers (S, P, D) ---")
        system_monitor._state = SystemState.NORMAL
        res = await call_middleware("/api/user/profile")
        headers = dict(res[0].get("headers", []))
        trace = headers.get(b"X-Middleware-Decision", b"").decode()
        logger.info(f"Trace Header: {trace}")
        if "S=NORMAL,P=HIGH,D=allow" in trace:
             logger.info("✅ Trace header format and content correct.")
        else:
             logger.error(f"❌ Trace header incorrect: {trace}")

        logger.info("✨ Task 1 verification complete.")
        
    except Exception as e:
        logger.error(f"❌ Task 1 verification failed: {e}", exc_info=True)
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(test_task1_middleware())
