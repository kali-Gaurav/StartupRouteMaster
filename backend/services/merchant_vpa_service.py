import logging
import random
import json
from datetime import datetime, date
from typing import List, Dict, Any, Optional
from services.cache_service import cache_service

logger = logging.getLogger(__name__)

class MerchantVPAService:
    """
    Task 4: Multi-VPA Merchant Load Balancer.
    Rotates VPAs based on volume, health, region, and resting state.
    """
    
    # Task 4.10: Per-region VPA assignment
    MERCHANT_VPAS = [
        {"vpa": "gauravnagar@okaxis", "name": "RouteMaster Node North", "weight": 5, "daily_limit": 100000, "region": "NORTH"},
        {"vpa": "routemaster@axl", "name": "RouteMaster Node South", "weight": 3, "daily_limit": 100000, "region": "SOUTH"},
        {"vpa": "emergency_vpa@okhdfc", "name": "RouteMaster Backup", "weight": 1, "daily_limit": 50000, "region": "ALL"}
    ]

    DAILY_VOLUME_PREFIX = "vpa_volume:"
    VPA_HEALTH_PREFIX = "vpa_health:"
    VPA_RESTING_PREFIX = "vpa_resting:"

    def get_vpa_volume(self, vpa: str) -> float:
        today = date.today().isoformat()
        key = f"{self.DAILY_VOLUME_PREFIX}{vpa}:{today}"
        return float(cache_service.get(key) or 0.0)

    def record_volume(self, vpa: str, amount: float):
        today = date.today().isoformat()
        key = f"{self.DAILY_VOLUME_PREFIX}{vpa}:{today}"
        current = self.get_vpa_volume(vpa)
        new_volume = current + amount
        cache_service.set(key, new_volume, ttl_seconds=86400 * 2) # 2 days TTL
        
        # Task 4.5: VPA "Resting" period after high burst volume (e.g. 50k in a short time)
        # If volume crosses 50% of the limit quickly, we rest it for 30 minutes
        for vpa_info in self.MERCHANT_VPAS:
            if vpa_info["vpa"] == vpa:
                if new_volume >= (vpa_info["daily_limit"] * 0.5) and current < (vpa_info["daily_limit"] * 0.5):
                    logger.warning(f"VPA {vpa} crossed 50% capacity burst. Entering RESTING state for 30 mins.")
                    self.set_resting(vpa, 1800) # 30 minutes

    def set_resting(self, vpa: str, duration_seconds: int):
        cache_service.set(f"{self.VPA_RESTING_PREFIX}{vpa}", "RESTING", ttl_seconds=duration_seconds)

    def is_resting(self, vpa: str) -> bool:
        return bool(cache_service.get(f"{self.VPA_RESTING_PREFIX}{vpa}"))

    def mark_health(self, vpa: str, status: str = "healthy"):
        key = f"{self.VPA_HEALTH_PREFIX}{vpa}"
        cache_service.set(key, status, ttl_seconds=86400) # 24 hour health status

    def get_health(self, vpa: str) -> str:
        key = f"{self.VPA_HEALTH_PREFIX}{vpa}"
        return cache_service.get(key) or "healthy"
        
    def get_dashboard_stats(self) -> List[Dict[str, Any]]:
        """Task 4.7: Real-time VPA utilization dashboard."""
        stats = []
        for vpa_info in self.MERCHANT_VPAS:
            vpa = vpa_info["vpa"]
            volume = self.get_vpa_volume(vpa)
            health = self.get_health(vpa)
            resting = self.is_resting(vpa)
            stats.append({
                "vpa": vpa,
                "name": vpa_info["name"],
                "region": vpa_info["region"],
                "utilization_pct": min(100.0, (volume / vpa_info["daily_limit"]) * 100),
                "volume": volume,
                "limit": vpa_info["daily_limit"],
                "health": health,
                "status": "RESTING" if resting else "ACTIVE"
            })
        return stats

    def get_next_vpa(self, user_region: str = "ALL") -> Dict[str, Any]:
        """
        Task 4.3 & 4.10: Weight-based rotation logic with region support.
        Excludes unhealthy VPAs, resting VPAs, and those exceeding limits.
        """
        available_vpas = []
        
        for vpa_info in self.MERCHANT_VPAS:
            vpa = vpa_info["vpa"]
            
            # 4.4 Auto-removal of blacklisted/blocked VPAs
            if self.get_health(vpa) != "healthy":
                continue
                
            # 4.5 Skip if resting
            if self.is_resting(vpa):
                continue
                
            # 4.10 Region matching (fallback to ALL if no match)
            if user_region != "ALL" and vpa_info["region"] not in [user_region, "ALL"]:
                continue
                
            # 4.2 Per-VPA daily volume tracking (₹1L limit)
            current_volume = self.get_vpa_volume(vpa)
            if current_volume >= vpa_info["daily_limit"]:
                logger.warning(f"VPA {vpa} reached its daily limit of {vpa_info['daily_limit']}.")
                continue
            
            # 4.8 Alert at 80% capacity
            if current_volume >= (vpa_info["daily_limit"] * 0.8):
                logger.info(f"VPA {vpa} is at 80%+ capacity (Current: {current_volume}).")

            # Add to pool based on weight
            for _ in range(vpa_info["weight"]):
                available_vpas.append(vpa_info)

        if not available_vpas:
            # If region lock failed, try without region lock
            if user_region != "ALL":
                logger.warning(f"No healthy VPAs for region {user_region}. Falling back to ALL regions.")
                return self.get_next_vpa("ALL")
                
            logger.error("CRITICAL: No healthy MERCHANT VPAs available. Returning Emergency VPA.")
            return self.MERCHANT_VPAS[-1] # Always return the emergency one as last resort

        selected = random.choice(available_vpas)
        logger.debug(f"Selected VPA {selected['vpa']} for payment (Region: {user_region}).")
        return selected

merchant_vpa_service = MerchantVPAService()
