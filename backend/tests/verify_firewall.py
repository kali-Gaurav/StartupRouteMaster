import asyncio
import logging
import sys
import os

# Set PYTHONPATH
sys.path.append(os.getcwd())

from core.nexus.security.firewall import nexus_firewall

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger("verify-firewall")

async def run_firewall_test():
    logger.info("🧪 Launching NEXUS-2.8: Firebase Integrated Firewall Security Test...")
    
    # 1. Test SSH Lockout Guard
    logger.info("🛡️ Testing Task 2.1: SSH Lockout Prevention...")
    
    result = await nexus_firewall.block_port(22)
    if result is False:
        logger.info("✅ SUCCESS: SSH port 22 block was rejected in security layer.")
    else:
        logger.error("❌ FAILURE: SSH port 22 block was allowed! Safety risk detected.")
        return 1

    # 2. Test Allow Port (Dry Run/Live)
    logger.info("🛡️ Testing Task 2.1: Port Permissions...")
    res = await nexus_firewall.allow_port(8080)
    
    if res:
        logger.info(f"✅ SUCCESS: Port 8080 permission granted in security layer.")
    else:
        logger.error("❌ FAILURE: Port 8080 permission denied.")
        return 1
        
    logger.info("🎉 Task 2.8 VERIFIED: VPS Security Perimeter (Firewall) is Active and Safe.")
    return 0

if __name__ == "__main__":
    sys.exit(asyncio.run(run_firewall_test()))
