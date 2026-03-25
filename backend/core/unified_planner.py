import asyncio
import logging
from typing import List
from schemas.unified_search import JourneyOption, UnifiedSearchRequest

logger = logging.getLogger(__name__)

class UnifiedPlanner:
    def __init__(self, adapters: List):
        self.adapters = adapters

    async def plan(self, req: UnifiedSearchRequest) -> List[JourneyOption]:
        """
        [Task 4.2] Agentic Planner - Phase-Based Expansion.
        1. Try Selective Search (Low transfer, fast engines).
        2. If results < threshold, try Discovery Search (Expanded hubs, higher transfers).
        """
        threshold = 3
        
        # --- PHASE 1: HIGH PERFORMANCE ---
        logger.info(f"Phase 1: Selective Search (Strict Mode) for {req.source}->{req.destination}")
        # Restrict constraints temporarily for Phase 1
        orig_max_transfers = req.constraints.max_transfers
        req.constraints.max_transfers = min(1, orig_max_transfers)
        
        # Use only high-speed engines (UltraTurbo)
        phase_1_results = await self._run_parallel_search(req, engines=["ultraturbo"])
        
        if len(phase_1_results) >= threshold:
            logger.info("Found sufficient Phase 1 results.")
            return self.rank(phase_1_results, req.preferences)[:req.max_results]

        # --- PHASE 2: EXHAUSTIVE DISCOVERY ---
        logger.info("Phase 1 yielded insufficient results. Expanding to Phase 2 (Relaxed Discovery)...")
        req.constraints.max_transfers = orig_max_transfers
        req.constraints.max_results = 50 # Increase sampling
        
        # Use all available adapters (TBR, RAPTOR, etc.)
        phase_2_results = await self._run_parallel_search(req)
        
        all_results = self._deduplicate(phase_1_results + phase_2_results)
        return self.rank(all_results, req.preferences)[:req.max_results]

    async def _run_parallel_search(self, req: UnifiedSearchRequest, engines: Optional[List[str]] = None) -> List[JourneyOption]:
        tasks = []
        for adapter in self.adapters:
            # Engine Filtering
            if engines and adapter.name not in engines:
                continue
            tasks.append(adapter.search(req))
            
        results = await asyncio.gather(*tasks, return_exceptions=True)
        journeys = []
        for res in results:
            if not isinstance(res, Exception) and res:
                journeys.extend(res)
        return journeys

    def _deduplicate(self, journeys: List[JourneyOption]) -> List[JourneyOption]:
        seen = set()
        unique = []
        for j in journeys:
            if j.journey_id not in seen:
                seen.add(j.journey_id)
                unique.append(j)
        return unique

    def rank(self, journeys: List[JourneyOption], preference: str) -> List[JourneyOption]:
        """
        Intelligent ranking based on user profile preferences.
        """
        def score_function(j: JourneyOption):
            if preference == "fastest":
                return j.total_duration
            
            if preference == "cheapest":
                return j.total_price
            
            if preference == "safest":
                return -j.safety_score # Lower is better for sort, so negate high safety
            
            # Balanced Scoring (w1*Time + w2*Price - w3*Safety)
            # Normalize scores mentally: 1 hour ~ 100 rupees
            return (j.total_duration * 0.5) + (j.total_price * 0.3) - (j.safety_score * 50)

        return sorted(journeys, key=score_function)
