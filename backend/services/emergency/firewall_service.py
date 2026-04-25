import logging
import time
from typing import Optional, Dict, Any
from services.cache_service import cache_service
from config import Config

logger = logging.getLogger("routemaster.emergency.firewall")

class TrafficGuardian:
    """
    [Task 4.5] L4/L7 Traffic Guardian.
    Acts as an autonomous firewall that blocks malicious IPs/Fingerprints.
    Interfaces with GuardianAgent and HealthSentinel.
    """
    BLOCK_KEY_PREFIX = "firewall_block:"
    BURST_KEY_PREFIX = "firewall_burst:"
    
    # Thresholds for autonomous blocking
    BURST_THRESHOLD = 50  # Requests per 10 seconds from one source
    WINDOW_SECONDS = 10
    DEFAULT_BLOCK_DURATION = 3600  # 1 Hour

    @staticmethod
    def is_blocked(source_id: str) -> bool:
        """
        Checks if the IP or Fingerprint is currently blacklisted.
        """
        block_data = cache_service.get(f"{TrafficGuardian.BLOCK_KEY_PREFIX}{source_id}")
        if block_data:
            logger.warning(f"🛡️ [FIREWALL] Rejected blocked source: {source_id} | Reason: {block_data.get('reason')}")
            return True
        return False

    @staticmethod
    def issue_block(source_id: str, reason: str, duration: int = DEFAULT_BLOCK_DURATION):
        """
        Manually or autonomously triggers a block command.
        """
        cache_service.set(
            f"{TrafficGuardian.BLOCK_KEY_PREFIX}{source_id}",
            {"reason": reason, "blocked_at": time.time()},
            ttl_seconds=duration
        )
        logger.critical(f"🛑 [FIREWALL] SOURCE BLOCKED: {source_id} | REASON: {reason} | DURATION: {duration}s")

    @staticmethod
    def log_and_check_burst(source_id: str, endpoint: str) -> bool:
        """
        Slide-window burst detection to prevent DDoS or Crawler spikes.
        Returns True if a burst is detected (should block).
        """
        key = f"{TrafficGuardian.BURST_KEY_PREFIX}{source_id}"
        count = cache_service.incr(key)
        
        if count == 1:
            cache_service.expire(key, TrafficGuardian.WINDOW_SECONDS)
            
        if count > TrafficGuardian.BURST_THRESHOLD:
            TrafficGuardian.issue_block(source_id, f"Aggressive Burst detected on {endpoint}", duration=7200)
            return True
            
        return False

    @staticmethod
    def evaluate_request(ip: str, fingerprint: Optional[str], endpoint: str) -> bool:
        """
        Primary pre-flight check for every L7 request.
        Returns False if request should be aborted.
        """
        # Check IP
        if TrafficGuardian.is_blocked(ip):
            return False
            
        # Check Fingerprint
        if fingerprint and TrafficGuardian.is_blocked(fingerprint):
            return False
            
        # Check Burst (DDoS Protection)
        if TrafficGuardian.log_and_check_burst(fingerprint or ip, endpoint):
            return False
            
        return True

firewall_guardian = TrafficGuardian()
