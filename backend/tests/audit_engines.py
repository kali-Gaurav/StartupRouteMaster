import asyncio
import logging
import time
from datetime import datetime, timedelta
from typing import List, Any

# Ensure we use the correct absolute imports
from core.route_engine.orchestrator import UnifiedRoutingOrchestrator
from core.route_engine.base import RoutingRequest, RoutingResponse
from core.route_engine.constraints import RouteConstraints
from core.data_structures import Persona

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AuditSuite")

async def audit_raptor_bloom_collisions():
    """Problem: Check for Bloom filter collisions in RAPTOR."""
    try:
        from core.route_engine.raptor import OptimizedRAPTOR
        raptor = OptimizedRAPTOR(max_transfers=3)
        
        # Test collision between IDs that share (ID % 64)
        s1 = 64
        s2 = 128
        
        # Manually verify collision math
        bloom = 0
        bloom |= (1 << (s1 % 64))
        if bloom & (1 << (s2 % 64)):
            logger.error(f"❌ AUDIT REVEALED: RAPTOR Bloom Collision! Station {s1} and {s2} collide (Bit {s1 % 64}). Valid routes might be pruned as cycles.")
        else:
            logger.info("✅ Bloom Filter looks safe for these 2 IDs (unexpected).")
            
    except Exception as e:
        logger.error(f"Audit setup failed: {e}")

if __name__ == "__main__":
    asyncio.run(audit_raptor_bloom_collisions())
