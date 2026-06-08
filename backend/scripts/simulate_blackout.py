import asyncio
import logging
import random
from typing import List, Dict
from services.mesh_protocol import MeshProtocolService
from services.sathi_location_service import SathiLocationService

# Configure logging for the simulation
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("chaos.blackout")

async def run_blackout_simulation():
    """
    [RM-QA-402] Execute a simulated network blackout and verify mesh relay.
    """
    logger.info("🌑 Starting Blackout Simulation: Regional Shard [NORTH]")
    
    # 1. Populate nodes (Sathis)
    sathi_ids = [f"SATHI_{i:03}" for i in range(50)]
    online_nodes = sathi_ids[:25]
    offline_nodes = sathi_ids[25:]
    
    logger.info(f"📍 Populating 50 nodes. 25 Online, 25 Offline (Blackout Zone).")
    
    # 2. Establish mesh topology (who can see whom)
    # Every offline node can see at least one online node (simulated proximity)
    for off_id in offline_nodes:
        relay_peer = random.choice(online_nodes)
        await MeshProtocolService.register_local_node(off_id, [relay_peer])
    
    logger.info("🕸️ Mesh topology established. Proximity discovery active.")

    # 3. Trigger SOS signals from the Blackout Zone
    test_signals = 10
    success_relays = 0
    deferred_syncs = 0
    
    logger.info(f"🚨 Triggering {test_signals} SOS alerts from the Offline zone...")
    
    for i in range(test_signals):
        originator = random.choice(offline_nodes)
        # Find who they can mesh with
        node_raw = await MeshProtocolService.register_local_node(originator, [random.choice(online_nodes)])
        
        # Simulate the relay
        incident_data = {
            "station_code": "NDLS",
            "type": "CRITICAL_SOS",
            "timestamp": "2026-05-01T00:15:00Z"
        }
        
        # The Offline node finds a neighbor to hop through
        # In a real app, this is done via BLE/mDNS
        relay_node = online_nodes[i % len(online_nodes)]
        
        result = await MeshProtocolService.relay_sos_signal(originator, relay_node, incident_data)
        
        if result["status"] == "RELAY_SUCCESS":
            success_relays += 1
            logger.info(f"✅ RELAY SUCCESS: {originator} -> {relay_node} -> Dispatcher")
        elif result["status"] == "DEFERRED_SYNC_QUEUED":
            deferred_syncs += 1
            logger.warning(f"📥 DEFERRED: {originator} signal queued for sync.")

    # 4. Final Verification
    logger.info("--- SIMULATION REPORT ---")
    logger.info(f"Total Test Signals: {test_signals}")
    logger.info(f"Relayed via Mesh:   {success_relays}")
    logger.info(f"Deferred (Offline): {deferred_syncs}")
    
    if success_relays == test_signals:
        logger.info("🏆 MESH PROTOCOL VERIFIED: 100% Signal Delivery through Blackout.")
    else:
        logger.error("⚠️ SIGNAL LOSS DETECTED: Review mesh density parameters.")

if __name__ == "__main__":
    asyncio.run(run_blackout_simulation())
