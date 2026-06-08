import logging
import json
import os
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime
from core.data_utils.structures import Route, Persona
from services.ml.availability_heuristic import availability_heuristic

logger = logging.getLogger("nexus.shadow")

class ShadowIntelligenceOrchestrator:
    """
    [Phase 3] Shadow Intelligence Auditor & Proactive Searcher.
    Intercepts routes and compares heuristic scores with predicted models.
    Also runs background 'Ghost Searches' for high-demand corridors to find yield gaps.
    """
    
    def __init__(self):
        self.audit_log: List[Dict[str, Any]] = []
        self.synthetic_export_path = "backend/data/training/synthetic_yield.json"
        os.makedirs(os.path.dirname(self.synthetic_export_path), exist_ok=True)

    async def audit_route_intelligence(self, route: Route, actual_status: Optional[str] = None):
        """
        Compares the AvailabilityHeuristic score with reality.
        """
        heuristic_score = availability_heuristic.get_route_availability_score(route.segments)
        
        # Mocking the Predictive Model for now
        mock_predictive_score = heuristic_score * 0.95 + 0.02
        
        delta = abs(heuristic_score - mock_predictive_score)
        
        audit_entry = {
            "timestamp": datetime.now().isoformat(),
            "route_id": getattr(route, 'route_id', 'unknown'),
            "heuristic_score": heuristic_score,
            "predictive_score": mock_predictive_score,
            "delta": delta,
            "actual_status": actual_status
        }
        
        if delta > 0.1:
            logger.warning(f"🚨 [SHADOW:ALERT] High Intelligence Gap ({delta:.2f}) on route {audit_entry['route_id']}")
            self._export_synthetic_data(audit_entry)
        
        logger.info(f"📊 [SHADOW:AUDIT] H:{heuristic_score:.2f} | P:{mock_predictive_score:.2f} | D:{delta:.4f}")
        return audit_entry

    async def run_ghost_search_loop(self):
        """
        Background loop that analyzes hot corridors and triggers ghost searches.
        """
        from services.intelligence.demand_service import demand_service
        from services.search_service import SearchService
        from database.session import SessionTransit
        
        logger.info("👻 [SHADOW:SIO] Ghost Search Loop started.")
        
        while True:
            try:
                # 1. Fetch Hot Corridors
                hot_corridors = demand_service.get_hot_corridors(limit=5)
                
                for corridor_str, score in hot_corridors:
                    origin, destination = corridor_str.split(":")
                    logger.info(f"🕵️ [SHADOW] Ghost Search triggered for {origin} -> {destination} (Demand Score: {score})")
                    
                    # 2. Run RAPTOR Search in background
                    async with SessionTransit() as db:
                        search_svc = SearchService(db)
                        results = await search_svc.search_routes(
                            source=origin,
                            destination=destination,
                            travel_date=datetime.now().strftime("%Y-%m-%d"),
                            budget_category=Persona.EXPERT.value, # Use Expert for thoroughness
                            limit=3
                        )
                        
                        # 3. Analyze Yield Gap
                        await self._analyze_yield_gap(corridor_str, results.get("journeys", []))
                
                # Sleep between cycles (Throttle via Nexus Governor placeholder)
                await asyncio.sleep(300) # 5 minutes
                
            except Exception as e:
                logger.error(f"Error in Ghost Search Loop: {e}")
                await asyncio.sleep(60)

    async def _analyze_yield_gap(self, corridor: str, routes: List[Route]):
        """Compares search results with 'Moat' expectations."""
        for route in routes:
            # Audit each found route
            await self.audit_route_intelligence(route)

    def _export_synthetic_data(self, entry: Dict[str, Any]):
        """Dumps high-delta audits for model retraining."""
        try:
            data = []
            if os.path.exists(self.synthetic_export_path):
                with open(self.synthetic_export_path, 'r') as f:
                    try:
                        data = json.load(f)
                    except json.JSONDecodeError:
                        data = []
            
            data.append(entry)
            # Keep only last 1000 entries
            data = data[-1000:]
            
            with open(self.synthetic_export_path, 'w') as f:
                json.dump(data, f, indent=4)
                
        except Exception as e:
            logger.error(f"Failed to export synthetic data: {e}")

shadow_orchestrator = ShadowIntelligenceOrchestrator()
