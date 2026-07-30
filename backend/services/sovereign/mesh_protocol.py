import logging
import json
import uuid
from datetime import datetime
from typing import List, Dict, Any, Optional
from core.infrastructure.redis_manager import async_redis_client

logger = logging.getLogger("nexus.mesh")

class MeshProtocolService:
    """
    [RM-I-402] Offline Mesh Protocol for Low-Connectivity Environments.
    Manages peer-to-peer signal relay and deferred audit synchronization.
    """
    MESH_NODE_PREFIX = "mesh_node:"
    PENDING_RECODE_KEY = "mesh_sync_queue"

    @staticmethod
    async def register_local_node(sathi_id: str, nearby_peers: List[str]):
        """
        Register a node's local visibility. 
        In real-world usage, this is triggered by Bluetooth/mDNS discovery.
        """
        node_data = {
            "sathi_id": sathi_id,
            "peers": nearby_peers,
            "last_mesh_ping": datetime.utcnow().isoformat(),
            "status": "MESH_ACTIVE"
        }
        await async_redis_client.set(f"{MeshProtocolService.MESH_NODE_PREFIX}{sathi_id}", json.dumps(node_data), ex=300)
        logger.debug(f"🕸️ [MESH] Node {sathi_id} heartbeat updated with {len(nearby_peers)} peers.")

    @staticmethod
    async def relay_sos_signal(originator_id: str, relay_node_id: str, incident_data: Dict[str, Any]):
        """
        [RM-I-402] Hop-based signal relay.
        If Originator has no signal, Relay Node pushes the incident to the API.
        """
        from services.safety_dispatch_manager import SafetyDispatchManager
        
        logger.info(f"⚡ [MESH] RELAY: Node {relay_node_id} is hopping SOS from {originator_id}")
        
        # Add mesh metadata to the incident
        incident_data["mesh_hop"] = {
            "relay_node": relay_node_id,
            "hop_count": incident_data.get("mesh_hop", {}).get("hop_count", 0) + 1,
            "relayed_at": datetime.utcnow().isoformat()
        }
        
        # Attempt to dispatch via the relay node's connection
        try:
            from services.safety_dispatch_manager import SafetyDispatchManager
            # We use the existing industrial dispatch manager
            # Using NDLS coordinates as default for the mesh simulation
            incident = await SafetyDispatchManager.create_incident(
                user_id=originator_id,
                lat=incident_data.get("lat", 28.6139),
                lon=incident_data.get("lon", 77.2090),
                incident_type="SOS"
            )
            return {"status": "RELAY_SUCCESS", "incident_id": incident["id"]}
        except Exception as e:
            logger.error(f"❌ [MESH] Relay Failure Detail for {originator_id} via {relay_node_id}: {e}")
            # If relay also has no signal, store locally for deferred sync
            await MeshProtocolService.queue_for_deferred_sync(originator_id, incident_data)
            return {"status": "DEFERRED_SYNC_QUEUED"}

    @staticmethod
    async def queue_for_deferred_sync(originator_id: str, data: Dict[str, Any]):
        """
        Store safety records in a local buffer for synchronization when internet returns.
        """
        record = {
            "originator_id": originator_id,
            "data": data,
            "captured_at": datetime.utcnow().isoformat(),
            "sync_id": str(uuid.uuid4())
        }
        await async_redis_client.lpush(MeshProtocolService.PENDING_RECODE_KEY, json.dumps(record))
        logger.warning(f"📥 [MESH] Offline signal stored for deferred sync. ID: {record['sync_id']}")

    @staticmethod
    async def process_sync_queue():
        """
        Worker task to push offline records to the Global Audit Ledger once connectivity is restored.
        """
        from services.safety_audit_service import SafetyAuditService
        
        while True:
            raw = await async_redis_client.rpop(MeshProtocolService.PENDING_RECODE_KEY)
            if not raw: break
            
            record = json.loads(raw)
            # Sync to Immutable Audit Ledger
            await SafetyAuditService.log_event(
                "OFFLINE_SIGNAL_SYNCED", 
                record["data"], 
                record["originator_id"]
            )
            logger.info(f"📤 [MESH] Successfully synced offline record {record['sync_id']} to Global Audit.")
