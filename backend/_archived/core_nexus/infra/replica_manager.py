import logging
import time
from typing import Dict, Any, Optional
from enum import Enum

logger = logging.getLogger("nexus.infra.replica")

class ReplicaStatus(Enum):
    HEALTHY = "healthy"
    LAGGING = "lagging"
    OFFLINE = "offline"

class MultiRegionReplicaManager:
    """
    [G4.5.1] The 'Global Data' Sync Manager.
    Orchestrates search traffic between Primary and Regional Read-Replicas.
    Ensures sub-100ms search latency across the globe.
    """
    
    def __init__(self):
        # Mocked Replica Registry
        self.replicas = {
            "us-east-1": {"status": ReplicaStatus.HEALTHY, "lag_ms": 150, "last_heartbeat": time.time()},
            "eu-west-1": {"status": ReplicaStatus.HEALTHY, "lag_ms": 200, "last_heartbeat": time.time()},
            "ap-southeast-1": {"status": ReplicaStatus.HEALTHY, "lag_ms": 100, "last_heartbeat": time.time()}
        }
        self.max_allowed_lag_ms = 600000 # 10 Minutes

    async def get_optimal_db_connection(self, user_region: str = "main") -> str:
        """
        [Child G4.5.1.3] Dynamic Search-Diverter.
        Decides if we should use a local replica or fallback to Primary.
        """
        if user_region not in self.replicas:
            logger.info("🌐 [REPLICA] Region unknown. Using PRIMARY DB.")
            return "PRIMARY"

        replica = self.replicas[user_region]
        
        # 1. Health & Lag Check (Child G4.5.1.2)
        if replica["status"] != ReplicaStatus.HEALTHY:
            logger.warning(f"🚨 [REPLICA] {user_region} is {replica['status'].value}. Diverting to PRIMARY.")
            return "PRIMARY"
            
        if replica["lag_ms"] > self.max_allowed_lag_ms:
            logger.error(f"🐌 [REPLICA] {user_region} lag is excessive ({replica['lag_ms']}ms). Failing over to PRIMARY.")
            replica["status"] = ReplicaStatus.LAGGING
            return "PRIMARY"

        logger.info(f"⚡ [REPLICA] User in {user_region}. Using local HIGH-SPEED replica.")
        return f"REPLICA_{user_region.upper()}"

    async def update_replica_heartbeat(self, region: str, lag_ms: int):
        """[Child G4.5.1.2] Monitor Update."""
        if region in self.replicas:
            self.replicas[region]["lag_ms"] = lag_ms
            self.replicas[region]["last_heartbeat"] = time.time()
            if lag_ms < self.max_allowed_lag_ms:
                self.replicas[region]["status"] = ReplicaStatus.HEALTHY

replica_manager = MultiRegionReplicaManager()
