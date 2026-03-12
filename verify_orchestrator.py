import asyncio
import httpx
import time
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify-orchestrator")

BASE_URL = "http://127.0.0.1:8000"

async def verify_orchestration():
    async with httpx.AsyncClient(timeout=30.0) as client:
        logger.info("Checking Orchestrator Health...")
        resp = await client.get(f"{BASE_URL}/api/health")
        data = resp.json()
        
        system = data.get("system", {})
        tasks = system.get("tasks", {})
        
        logger.info(f"System Uptime: {system.get('uptime_seconds')}s")
        logger.info(f"Managed Tasks Found: {list(tasks.keys())}")
        
        critical_tasks = ["event_loop_monitor", "hardware_monitor", "db_conn_reaper"]
        for t in critical_tasks:
            if t in tasks:
                status = tasks[t]
                logger.info(f"Task '{t}': Running={status['is_running']}, Failures={status['failure_count']}")
                assert status["is_running"] is True
            else:
                logger.error(f"❌ Critical task '{t}' NOT found in orchestrator!")
                assert False

        logger.info("✅ SystemOrchestrator Verified. All background services managed and healthy.")

if __name__ == "__main__":
    asyncio.run(verify_orchestration())
