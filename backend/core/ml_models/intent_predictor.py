import time
import asyncio
import logging
import re
import math # Moved to top
from typing import Dict, List, Optional, Tuple, Any

logger = logging.getLogger("intent-predictor")

class BayesianIntentPredictor:
    """
    Subtask 1.12: Predictive Engine with Hard SLA (P99 < 2ms).
    """
    def __init__(self):
        self.priors = {
            "SEARCH": 0.5, "BOOKING": 0.2, "STATUS": 0.2, "ADMIN": 0.05, "OTHER": 0.05
        }
        self.intent_map = {
            "search": "SEARCH", "find": "SEARCH",
            "book": "BOOKING", "pay": "BOOKING",
            "live": "STATUS", "track": "STATUS",
            "admin": "ADMIN", "health": "OTHER", "status": "OTHER"
        }
        regex_pattern = "|".join(rf"\b{re.escape(k)}\b" for k in self.intent_map.keys())
        self.regex = re.compile(regex_pattern, re.IGNORECASE)
        self.sla_threshold_ms = 2.0 

    async def predict_with_sla(self, method: str, path: str, headers: Dict[str, str]) -> Tuple[str, float, bool]:
        start = time.perf_counter()
        try:
            intent, conf = await asyncio.wait_for(
                self._predict_core(method, path, headers),
                timeout=self.sla_threshold_ms / 1000.0
            )
            duration_ms = (time.perf_counter() - start) * 1000
            return intent, conf, (duration_ms <= self.sla_threshold_ms)
        except asyncio.TimeoutError:
            return "SEARCH", 0.5, False
        except Exception:
            return "OTHER", 0.0, False

    async def _predict_core(self, method: str, path: str, headers: Dict[str, str]) -> Tuple[str, float]:
        path_lower = path.lower()
        scores = {intent: 0.0 for intent in self.priors.keys()}
        matches = self.regex.findall(path_lower)
        for match in matches:
            intent = self.intent_map.get(match.lower())
            if intent: scores[intent] += 5.0
        
        if method == "POST": scores["BOOKING"] += 1.0
        elif method == "GET": scores["SEARCH"] += 0.5
        if "mobile" in headers.get("user-agent", "").lower():
            scores["STATUS"] += 0.5

        final_probs = {}
        for intent, prior in self.priors.items():
            final_probs[intent] = math.exp(math.log(prior) + scores[intent])

        total = sum(final_probs.values())
        normalized = {k: v / total for k, v in final_probs.items()}
        best = max(normalized, key=normalized.get)
        return best, normalized[best]

intent_predictor = BayesianIntentPredictor()
