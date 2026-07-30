import logging
import json
from typing import Dict, Any, Optional, List
from datetime import datetime
from core.infrastructure.redis_manager import redis_client

logger = logging.getLogger("intelligence.demand")

class DemandService:
    """
    Captures real-time user intent (searches) to identify 'Hot Corridors'.
    Used by SIO for ghost-searches and by Orchestrator for route biasing.
    """
    
    HEATMAP_KEY_PREFIX = "demand:heatmap"
    HOT_CORRIDORS_KEY = "demand:hot_corridors"
    
    def log_search_intent(self, origin: str, destination: str, persona: str = "generic"):
        """
        Increment demand for a specific corridor.
        Keys are organized by hour to allow temporal analysis.
        """
        hour_key = datetime.now().strftime("%Y-%m-%d:%H")
        corridor = f"{origin}:{destination}"
        
        # 1. Update temporal heatmap
        heatmap_key = f"{self.HEATMAP_KEY_PREFIX}:{hour_key}"
        try:
            redis_client.hincrby(heatmap_key, corridor, 1)
            redis_client.expire(heatmap_key, 86400 * 7)  # Keep for 7 days
            
            # 2. Update global hot corridors (Sorted Set)
            redis_client.zincrby(self.HOT_CORRIDORS_KEY, 1, corridor)
            
            logger.info(f"📈 [DEMAND] Logged intent: {corridor} | Persona: {persona}")
        except Exception as e:
            logger.error(f"Failed to log demand: {e}")

    def get_hot_corridors(self, limit: int = 10) -> List[tuple]:
        """Returns the top N corridors by total demand."""
        try:
            results = redis_client.zrevrange(self.HOT_CORRIDORS_KEY, 0, limit - 1, withscores=True)
            return [(r[0].decode('utf-8'), r[1]) for r in results]
        except Exception as e:
            logger.error(f"Failed to fetch hot corridors: {e}")
            return []

    def get_corridor_demand(self, origin: str, destination: str) -> float:
        """Returns the normalized demand score for a corridor."""
        corridor = f"{origin}:{destination}"
        try:
            score = redis_client.zscore(self.HOT_CORRIDORS_KEY, corridor)
            if not score:
                return 0.0
            
            # Normalize against max score
            max_score = redis_client.zscore(self.HOT_CORRIDORS_KEY, 
                                          redis_client.zrevrange(self.HOT_CORRIDORS_KEY, 0, 0)[0]) or 1.0
            return float(score) / float(max_score)
        except Exception as e:
            logger.error(f"Failed to get corridor demand: {e}")
            return 0.0

demand_service = DemandService()
