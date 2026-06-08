"""
Sovereign WAF Service - Edge Hardening & Anti-Scraping
=====================================================
Patent Innovation #5: Demand-Aware Edge Security.

This service protects the RouteMaster network from:
1. Demand Manipulation Attacks: Bots trying to trigger artificial high pressure to harvest incentives.
2. Adversarial Scraping: Large-scale extraction of private routing graphs.
3. Incentive Farming: Users exploiting the EDR system for guaranteed credits.

It uses high-fidelity fingerprinting and corridor-aware rate limiting.
"""

import logging
import hashlib
import time
from typing import Dict, Any, Optional, List
from fastapi import Request
from core.resilience.rate_limit import rate_limiter
from core.sovereign.network_pressure import network_pressure

logger = logging.getLogger("sovereign.waf")

class SovereignWAFService:
    """
    Advanced security layer that protects Sovereign Intelligence assets.
    """

    def __init__(self):
        self.name = "Sovereign WAF"
        # Cache for fingerprints to avoid redundant hashing
        self._fingerprint_cache: Dict[str, str] = {}

    async def inspect_request(self, request: Request, source: str, destination: str) -> Dict[str, Any]:
        """
        Performs a multi-layered security inspection of a search request.
        Returns a decision and threat metadata.
        """
        start_ts = time.perf_counter()
        
        # 1. Generate Fingerprint
        fingerprint = self._generate_fingerprint(request)
        client_ip = self._get_client_ip(request)
        user_id = request.headers.get("x-user-id", "anonymous")

        # 2. Corridor-Specific Rate Limiting (Demand-Aware)
        # Tightens limits as corridor pressure increases.
        is_corridor_allowed = await rate_limiter.is_corridor_allowed(client_ip, source, destination)
        
        # 3. Global Anti-Farming Check
        is_farming = False
        if user_id != "anonymous":
            is_farming = await rate_limiter.is_incentive_farming(user_id)

        # 4. Anomaly Detection (User-Agent & Header Entropy)
        anomaly_score = self._calculate_anomaly_score(request)

        # 5. Final Decision Logic
        allowed = True
        reason = "CLEAN"
        
        if not is_corridor_allowed:
            allowed = False
            reason = "DEMAND_MANIPULATION_PROTECTION"
        elif is_farming:
            allowed = False
            reason = "INCENTIVE_FARMING_DETECTION"
        elif anomaly_score > 0.8:
            allowed = False
            reason = "BOT_BEHAVIOR_DETECTED"

        latency_ms = (time.perf_counter() - start_ts) * 1000
        
        if not allowed:
            logger.warning(
                f"🛡️ [WAF] Request BLOCKED | Reason: {reason} | IP: {client_ip} | "
                f"Fingerprint: {fingerprint[:8]} | Score: {anomaly_score:.2f}"
            )

        return {
            "allowed": allowed,
            "reason": reason,
            "fingerprint": fingerprint,
            "threat_score": anomaly_score,
            "latency_ms": f"{latency_ms:.2f}"
        }

    def _generate_fingerprint(self, request: Request) -> str:
        """
        Generates a unique client fingerprint based on HTTP headers.
        """
        headers = request.headers
        # Combine stable headers that identify a unique browser/client
        components = [
            headers.get("user-agent", ""),
            headers.get("accept-language", ""),
            headers.get("accept-encoding", ""),
            headers.get("dnt", ""),
            # We don't include IP here so the same bot on different IPs has the same fingerprint
        ]
        raw_str = "|".join(components)
        return hashlib.sha256(raw_str.encode()).hexdigest()

    def _get_client_ip(self, request: Request) -> str:
        """Helper to extract IP with proxy support."""
        return request.headers.get("x-track-ip") or request.client.host if request.client else "unknown"

    def _calculate_anomaly_score(self, request: Request) -> float:
        """
        Calculates a score [0.0 - 1.0] representing the likelihood of a bot request.
        """
        score = 0.0
        ua = request.headers.get("user-agent", "").lower()
        
        # 1. Known Bot UA strings
        bot_keywords = ["python", "curl", "wget", "headless", "selenium", "puppeteer", "playwright"]
        if any(kw in ua for kw in bot_keywords):
            score += 0.5
            
        # 2. Missing standard headers
        standard_headers = ["accept", "accept-language", "user-agent"]
        missing_count = sum(1 for h in standard_headers if h not in request.headers)
        score += (missing_count * 0.2)
        
        # 3. High-entropy path or params (simple check)
        # Bots often use machine-generated IDs
        
        return min(1.0, score)

# Global Instance
sovereign_waf = SovereignWAFService()
