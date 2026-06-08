import logging
import json
import time
from datetime import datetime
from typing import Dict, Any, List
from core.infrastructure.redis_manager import async_redis_client

logger = logging.getLogger("nexus.mesh_sync")

class MeshSyncService:
    """
    [RM-S-902] Offline Mesh Relay & Sathi Presence.
    Handles 'Ghost' presence packets from low-connectivity corridors.
    """
    
    MESH_QUEUE = "mesh:relay_queue"
    PRESENCE_PREFIX = "mesh:presence:"

    @staticmethod
    async def ingest_mesh_packet(source_sathi: str, packet_data: Dict[str, Any]):
        """
        [Council Feature] Ingest a packet carried from an offline zone by a relay node.
        """
        payload = {
            "sathi_id": source_sathi,
            "lat": packet_data.get("lat"),
            "lon": packet_data.get("lon"),
            "timestamp": packet_data.get("timestamp"),
            "status": packet_data.get("status", "ACTIVE"),
            "relay_path": packet_data.get("relay_path", []) + [source_sathi],
            "ingested_at": datetime.utcnow().isoformat()
        }
        
        # 1. Update the 'Shadow' Presence in Redis
        await async_redis_client.set(
            f"{MeshSyncService.PRESENCE_PREFIX}{source_sathi}", 
            json.dumps(payload),
            ex=3600 # 1 hour TTL for mesh presence
        )
        
        # 2. Add to processing queue for global sharding sync
        await async_redis_client.lpush(MeshSyncService.MESH_QUEUE, json.dumps(payload))
        
        logger.info(f"🛰️ [MESH] Ingested relay packet for Sathi {source_sathi} (Relay Hops: {len(payload['relay_path'])})")
        return True

    @staticmethod
    async def pre_warm_local_nodes(station_code: str, sathi_ids: List[str]):
        """
        [Patent Upgrade: Anticipatory Pre-warming]
        Caches Sathi heartbeats on mobile nodes (trains) before entering signal dead zones.
        """
        for sathi_id in sathi_ids:
            # Fetch current state from global shard
            state = await async_redis_client.get(f"sathi:state:{sathi_id}")
            if state:
                # Cache on the 'Next Station' buffer for mesh transition
                await async_redis_client.set(
                    f"mesh:pre_warm:{station_code}:{sathi_id}", 
                    state,
                    ex=600 # 10 minute pre-warm TTL
                )
        
        logger.info(f"⚡ [MESH:PREWARM] Pre-warmed {len(sathi_ids)} Sathi nodes for Corridor: {station_code}")
        return True

if __name__ == "__main__":
    # Test packet ingestion
    import asyncio
    async def test():
        await MeshSyncService.ingest_mesh_packet("SATHI_BIHAR_01", {"lat": 25.0, "lon": 85.0, "timestamp": time.time()})
    asyncio.run(test())
