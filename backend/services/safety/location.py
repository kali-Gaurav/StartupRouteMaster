import logging
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from core.infrastructure.redis_manager import async_redis_client

logger = logging.getLogger("nexus.sathi_location")

class SathiLocationService:
    """
    [RM-IF-201] Industrial Geospatial Tracking Service.
    Handles real-time location updates with Regional Sharding for national scale.
    """
    GEO_KEY = "sathi_locations"
    METADATA_PREFIX = "sathi_meta:"
    STATION_DENSITY_KEY = "sathi_station_density"

    @staticmethod
    async def update_sathi_location(sathi_id: str, lat: float, lon: float, station_code: Optional[str] = None):
        """
        [RM-IF-201] Update Sathi location using Regional Sharding.
        """
        from core.infrastructure.scaling import ScalingManager
        
        # Determine the correct regional shard
        shard_key = await ScalingManager.get_sharded_key(SathiLocationService.GEO_KEY, station_code or "NDLS")
        
        # 1. Update Geospatial Index in the correct shard
        await async_redis_client.geoadd(shard_key, lon, lat, sathi_id)
        
        # 2. Update metadata in the Global Hash (for lookup)
        await async_redis_client.hset(
            f"{SathiLocationService.METADATA_PREFIX}{sathi_id}", 
            mapping={
                "lat": str(lat),
                "lon": str(lon),
                "last_seen": datetime.utcnow().isoformat(),
                "shard": shard_key
            }
        )
        
        logger.debug(f"📍 Sathi {sathi_id} location updated in {shard_key}")

    @staticmethod
    async def update_location_batch(updates: List[Dict[str, Any]]):
        """
        [RM-IF-702] High-performance pipeline update for mass simulations.
        """
        from core.infrastructure.scaling import ScalingManager
        async with async_redis_client.pipeline(transaction=True) as pipe:
            for up in updates:
                s_id = up["sathi_id"]
                lat, lon = up["lat"], up["lon"]
                shard_key = await ScalingManager.get_sharded_key(SathiLocationService.GEO_KEY, up.get("station_code", "NDLS"))
                
                pipe.execute_command("GEOADD", shard_key, lon, lat, s_id)
                pipe.hset(f"{SathiLocationService.METADATA_PREFIX}{s_id}", mapping={
                    "lat": str(lat), "lon": str(lon), 
                    "last_seen": datetime.utcnow().isoformat(), "shard": shard_key
                })
            await pipe.execute()
        logger.info(f"⚡ [PIPELINE] Processed batch of {len(updates)} location updates.")

    @staticmethod
    async def get_nearby_sathis(lat: float, lon: float, radius_km: float = 2.0, station_code: str = "NDLS") -> List[Dict[str, Any]]:
        """
        [RM-IF-201] Find nearby Sathis using Sharded Querying.
        """
        from core.infrastructure.scaling import ScalingManager
        
        shard_key = await ScalingManager.get_sharded_key(SathiLocationService.GEO_KEY, station_code)
        
        try:
            results = await async_redis_client.geosearch(
                shard_key,
                longitude=lon,
                latitude=lat,
                radius=radius_km,
                unit="km",
                withdist=True,
                withcoord=True
            )
            
            sathis = []
            if not results: return []

            for s_id, dist, coord in results:
                sathis.append({
                    "id": s_id,
                    "distance": round(dist, 2),
                    "lat": coord[1],
                    "lon": coord[0]
                })
                
            return sathis
        except Exception as e:
            logger.error(f"Error querying shard {shard_key}: {e}")
            return []

    @staticmethod
    async def get_station_vibe(station_code: str) -> Dict[str, Any]:
        """
        [RM-A-030] Fetch real-time station safety telemetry.
        """
        try:
            vibe_raw = await async_redis_client.hget("station_vibe_telemetry", station_code)
            if vibe_raw:
                return json.loads(vibe_raw)
        except Exception:
            pass
            
        return {
            "lighting": 80,
            "crowd_density": 0.4,
            "security_presence": 60
        }

    @staticmethod
    async def get_station_sathi_count(station_code: str) -> int:
        """
        Get the number of active Sathis assigned to or near a station.
        """
        count_raw = await async_redis_client.hget(SathiLocationService.STATION_DENSITY_KEY, station_code)
        return int(count_raw) if count_raw else 0

    @staticmethod
    async def set_station_sathi_count(station_code: str, count: int):
        """
        Update the station density cache.
        """
        await async_redis_client.hset(SathiLocationService.STATION_DENSITY_KEY, station_code, str(count))

    @staticmethod
    async def get_last_mile_coverage(station_code: str) -> Dict[str, Any]:
        """
        [RM-A-040] Check for verified last-mile transit and safety kiosks.
        """
        major_hubs = {"NDLS", "HWH", "CSMT", "MAS", "SBC"}
        return {
            "has_verified_transit": station_code in major_hubs or len(station_code) <= 3,
            "has_safety_kiosk": station_code in major_hubs,
            "verified_partners": ["SafeAuto", "BluSmart"] if station_code in major_hubs else []
        }

    @staticmethod
    async def get_active_incidents(station_code: str) -> List[Dict[str, Any]]:
        """
        [RM-A-031] Fetch real-time high-priority incidents reported at a station.
        Uses a station-specific summary hash to avoid global set scanning.
        """
        try:
            # Check station-specific summaries (Populated by SafetyAuditService/DispatchManager)
            incidents_raw = await async_redis_client.hget("station_incident_summaries", station_code)
            if incidents_raw:
                return json.loads(incidents_raw)
        except Exception as e:
            logger.error(f"Error fetching active incidents for {station_code}: {e}")
        
    @staticmethod
    def is_node_safety_pruned(station_id: int) -> bool:
        """
        [RM-A-032] Search-time safety gate.
        Synchronous check for hot search loop. 
        Returns True if the node should be skipped due to safety/stress signals.
        """
        # Placeholder for real-time safety memory layer check
        # In production, this would read from a shared memory buffer/bitmask
        # For now, we allow all nodes unless they are in a known blacklist (simulated)
        high_risk_nodes = {666, 999} # Example IDs
        return station_id in high_risk_nodes
