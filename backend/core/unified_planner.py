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
        Executes all mode adapters in parallel and merges/ranks results.
        """
        # --- PARALLEL EXECUTION (Upgrade 6) ---
        tasks = [adapter.search(req) for adapter in self.adapters]
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        all_journeys = []
        for res in results:
            if isinstance(res, Exception):
                logger.error(f"Planner Engine Failure: {res}")
                continue
            if res:
                all_journeys.extend(res)

        # --- RANKING ENGINE (Upgrade 1) ---
        ranked = self.rank(all_journeys, req.preferences)
        
        return ranked[:req.max_results]

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
