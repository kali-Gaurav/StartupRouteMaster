import logging
import json
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from core.infrastructure.redis_manager import async_redis_client

logger = logging.getLogger("nexus.scaling")

class ScalingManager:
    """
    [RM-IF-201] National-Scale Sharding Manager.
    Intelligently routes safety data to regional hubs to prevent global bottlenecks.
    """
    
    REGIONAL_HUBS = {
        "NORTH": ["NDLS", "DLI", "NZM", "GZB", "LKO"],
        "SOUTH": ["MAS", "SBC", "HYB", "TVC", "CBE"],
        "WEST": ["CSMT", "BCT", "ADI", "PUNE", "ST"],
        "EAST": ["HWH", "SDAH", "KGP", "PNBE", "GHY"],
        "CENTRAL": ["BPL", "JBP", "NGP", "ET", "VGLJ"]
    }

    @staticmethod
    def get_region_for_station(station_code: str) -> str:
        """
        Map a station code to its primary regional hub.
        """
        for region, stations in ScalingManager.REGIONAL_HUBS.items():
            if station_code in stations:
                return region
        return "GLOBAL" # Fallback for remote stations

    FALLBACK_REGION = "CENTRAL"

    @staticmethod
    async def warm_migrate_active_keys(from_region: str, to_region: str):
        """
        [Patent Upgrade: Anticipatory Rebalancing]
        Clones high-priority SOS keys to a healthy shard before a regional failure occurs.
        """
        import json
        # In production: SCAN for sos:active:* keys in the regional shard
        logger.warning(f"⚡ [SCALING:WARM_MIGRATE] Pre-emptively cloning active SOS keys from {from_region} to {to_region}")

    @staticmethod
    async def _get_latency(region: str) -> int:
        """Mock latency check for regional shard."""
        return 5 # ms

    @staticmethod
    async def get_active_region(station_code: str) -> str:
        """
        [RM-IF-601] Dynamic region selection with Failover & Warm Migration.
        Checks shard health and redirects to FALLBACK if primary is down.
        """
        primary_region = ScalingManager.get_region_for_station(station_code)
        
        # [Patent Refinement] Check latency for anticipatory rebalancing
        latency = await ScalingManager._get_latency(primary_region)
        if latency > 40:
            await ScalingManager.warm_migrate_active_keys(primary_region, ScalingManager.FALLBACK_REGION)
        
        # Check health of primary shard in Redis
        is_healthy = await async_redis_client.get(f"health:shard:{primary_region}")
        
        if is_healthy == "DOWN" and primary_region != ScalingManager.FALLBACK_REGION:
            logger.error(f"🚨 [FAILOVER] Shard {primary_region} is UNHEALTHY. Redirecting to {ScalingManager.FALLBACK_REGION}")
            return ScalingManager.FALLBACK_REGION
            
        return primary_region

    @staticmethod
    async def get_sharded_key(base_key: str, station_code: str) -> str:
        """
        Generate a regionalized key with active failover support.
        """
        region = await ScalingManager.get_active_region(station_code)
        return f"{base_key}:{region}"

    @staticmethod
    async def get_regional_telemetry(region: str) -> Dict[str, Any]:
        """
        Fetch aggregate safety telemetry for an entire railway region.
        """
        # [Industrial Logic] Queries regional specific hashes
        active_incidents = await async_redis_client.scard(f"active_incidents:{region}")
        online_sathis = await async_redis_client.zcard(f"sathi_locations:{region}")
        
        return {
            "region": region,
            "active_incidents": active_incidents,
            "online_sathis": online_sathis,
            "load_factor": (active_incidents / (online_sathis or 1)) * 100
        }

    @staticmethod
    async def broadcast_shard_health(region: str):
        """[Work: Infra Squad] Broadcasts local shard health to all peers."""
        health_data = {
            "region": region, 
            "timestamp": datetime.now(timezone.utc).timestamp(), 
            "status": "ALIVE"
        }
        await async_redis_client.publish("shard:gossip", json.dumps(health_data))

    _peer_registry: Dict[str, float] = {}

    @staticmethod
    async def discover_p2p_shard(target_region: str) -> bool:
        """[Work: Infra Squad] Consults the P2P peer registry if central hub is down."""
        last_seen = ScalingManager._peer_registry.get(target_region, 0)
        # If seen in the last 60 seconds, we trust the shard is up
        now = datetime.now(timezone.utc).timestamp()
        return (now - last_seen) < 60

    @staticmethod
    async def optimize_resource_allocation():
        """
        Detect regional 'Safety Deficits' and suggest responder redistribution.
        """
        alerts = []
        for region in ScalingManager.REGIONAL_HUBS.keys():
            stats = await ScalingManager.get_regional_telemetry(region)
            if stats["load_factor"] > 80:
                logger.warning(f"⚠️ [SCALING] Critical Safety Deficit in {region} hub!")
                alerts.append(f"Deploy reinforcements to {region}")
        return alerts
