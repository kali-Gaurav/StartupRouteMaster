import logging
import time
from fastapi import Request, HTTPException

logger = logging.getLogger("nexus.gatekeeper")

START_TIME = time.time()

async def nexus_gatekeeper(request: Request):
    """
    [Subtask 1.10] Master Operational Firewall for Nexus V3 Fiber.
    This function is a global dependency that checks system state before allowing a request.
    """
    # 0. Zero-Latency L0 Fast-Path Check [Task 41.1]
    from core.nexus.cache.mmap_cortex import nexus_cortex
    if nexus_cortex.is_kill_switch_active():
        logger.critical("[GATEKEEPER] Master Kill Switch ACTIVE. Blocking traffic.")
        raise HTTPException(status_code=503, detail="NEXUS_SYSTEM_HALTED")
        
    if nexus_cortex.is_panic():
        logger.critical("[GATEKEEPER] Global Financial Panic ACTIVE. Blocking traffic.")
        raise HTTPException(status_code=503, detail="NEXUS_FINANCIAL_BLACKOUT")

    # 1. Protocol Branding
    request.state.nexus_version = "3.1.0"
    request.state.nexus_uptime = round(time.time() - START_TIME, 2)
    
    return True
