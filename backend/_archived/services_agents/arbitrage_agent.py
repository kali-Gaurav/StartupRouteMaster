"""
Phase 8: Multi-Modal Arbitrage & Intermodal Logistics Agent
===========================================================
This agent identifies price/time gaps across different transport modes
(Rail, Bus, Flight) and suggests 'Arbitrage' opportunities to users.
It also handles 'Intermodal Logistics'—combining modes to bypass bottlenecks.
"""

import logging
import asyncio
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from services.agents.base_agent import BaseAgent, AgentStatus, AgentPriority
from services.providers.factory import provider_factory

logger = logging.getLogger("agent.arbitrage")

class MultiModalArbitrageAgent(BaseAgent):
    """
    Phase 8: Multi-Modal Arbitrage & Intermodal Logistics
    Discovers 'Release Valve' travel alternatives when primary routes are congested.
    """
    
    name = "ArbitrageAgent"
    description = "Discovers cross-modal travel alternatives and arbitrage opportunities"
    category = "optimization"
    priority = AgentPriority.HIGH
    icon = "🔓"
    color = "#F59E0B" # Amber

    def __init__(self):
        super().__init__()
        self.kg = None
        self._kg_available = False
        try:
            from services.knowledge_graph_service import TravelKnowledgeGraph
            self.kg = TravelKnowledgeGraph()
            self._kg_available = True
        except Exception as exc:
            logger.warning("Knowledge graph unavailable for ArbitrageAgent: %s", exc)
        self.auto_schedule_interval = 300  # Run every 5 minutes
        self._is_enabled = True

    async def initialize(self):
        """Warm up the KG connections."""
        logger.info(f"[{self.name}] Initializing Multi-Modal Arbitrage Layer...")
        if self.kg and hasattr(self.kg, "initialize"):
            await self.kg.initialize()

    async def execute(self, context: Optional[Dict] = None) -> Dict[str, Any]:
        """
        Main execution pulse.
        1. Identify 'High Pressure' routes (high WL or low availability).
        2. Search alternative modes (Bus/Flight) for those routes.
        3. Suggest 'Arbitrage' candidates to the KG.
        """
        start_time = datetime.now()
        logger.info(f"[{self.name}] Scanning for Multi-Modal Arbitrage opportunities...")

        # 1. Get routes with high demand (WL > threshold)
        # This would typically come from the Knowledge Graph or DemandForecaster
        hot_routes = await self._get_high_pressure_routes()
        
        arbitrage_found = 0
        intermodal_links = 0

        for route in hot_routes:
            src, dst = route['source'], route['destination']
            
            # 2. Check Bus Alternatives
            bus_options = await self._search_modal_alternative(src, dst, "bus")
            if bus_options:
                await self._process_arbitrage(route, bus_options, "bus")
                arbitrage_found += 1

            # 3. Check Intermodal 'Leapfrog' (Train -> Bus -> Train)
            # This is complex; we look for intermediate hubs
            hubs = await self.kg.get_intermediate_hubs(src, dst) if self.kg else []
            for hub in hubs[:3]: # Limit to top 3 hubs
                split_options = await self._find_intermodal_split(src, hub, dst)
                if split_options:
                    await self._record_intermodal_route(src, dst, split_options)
                    intermodal_links += 1

        duration = (datetime.now() - start_time).total_seconds()
        
        result = {
            "status": "success",
            "arbitrage_candidates": arbitrage_found,
            "intermodal_links_discovered": intermodal_links,
            "duration_seconds": duration
        }
        
        self.last_run = datetime.now()
        return result

    async def _get_high_pressure_routes(self) -> List[Dict]:
        """Identify routes where rail availability is critically low."""
        # Mocking for now, in production this queries the KG or SeatInventory
        return [
            {"source": "NDLS", "destination": "BCT", "rail_wl": 120},
            {"source": "SBC", "destination": "MAS", "rail_wl": 85},
            {"source": "HWH", "destination": "NDLS", "rail_wl": 150}
        ]

    async def _search_modal_alternative(self, src: str, dst: str, mode: str) -> List[Dict]:
        """Query external providers for alternative modal availability."""
        try:
            # provider_factory is part of G8 infrastructure
            provider = provider_factory.get_best_provider(mode)
            if not provider:
                return []
            
            # Use tomorrow's date for mock scan
            scan_date = (datetime.now() + timedelta(days=1)).strftime("%Y-%m-%d")
            return await provider.search(src, dst, scan_date)
        except Exception as e:
            logger.error(f"Error searching {mode} alternatives: {e}")
            return []

    async def _process_arbitrage(self, rail_route: Dict, alternatives: List[Dict], mode: str):
        """Analyze if an alternative mode qualifies as a valid 'Arbitrage' suggestion."""
        for alt in alternatives:
            # Heuristic: If Alt is faster or cheaper OR significantly more available (WL vs Confirmed)
            if alt.get('is_verified') and alt.get('total_cost', 0) > 0:
                if not self.kg:
                    logger.debug("Skipping KG write for arbitrage candidate because KG is unavailable.")
                    continue
                # Add to KG as a 'Release Valve' edge
                await self.kg.add_release_valve(
                    src=rail_route['source'],
                    dst=rail_route['destination'],
                    mode=mode,
                    data={
                        "alt_id": alt.get('id'),
                        "cost": alt.get('total_cost'),
                        "duration": alt.get('duration_minutes'),
                        "confidence": 0.85
                    }
                )

    async def _find_intermodal_split(self, src: str, hub: str, dst: str) -> Optional[Dict]:
        """Discover if a split route (Mode A -> Hub -> Mode B) is viable."""
        # logic for splitting journey: e.g., Train to Hub + Bus to Dst
        # This requires matching arrival(Hub) < departure(Hub) + buffer
        return None # Placeholder for complex logic

    async def _record_intermodal_route(self, src: str, dst: str, split_data: Dict):
        """Persist a discovered intermodal logistics route."""
        logger.info(f"🔗 [ARBITRAGE] Discovered intermodal route: {src} -> {dst} via split")

    def to_dict(self) -> Dict[str, Any]:
        data = super().to_dict()
        data.update({
            "kg_connected": self._kg_available,
            "arbitrage_threshold": 0.2 # 20% price diff
        })
        return data

    async def find_arbitrage_routes(self, source: str, destination: str, travel_date: datetime) -> List[Any]:
        """
        Public API for SearchService to fetch cross-modal alternatives.
        """
        logger.info(f"🔍 [ARBITRAGE] Finding release valves for {source} -> {destination}")
        
        # 1. Check Knowledge Graph for existing high-confidence patterns
        kg_valves = await self.kg.get_release_valves(source, destination) if self.kg else []
        
        results = []
        from core.data_utils.structures import Route, RouteSegment
        
        # 2. Convert KG valves to Route objects
        for valve in kg_valves:
            route = Route()
            # Standardize segments
            segment = RouteSegment(
                train_number=f"ALT-{valve['mode'].upper()}",
                train_name=f"Alternative {valve['mode'].capitalize()}",
                departure_code=source,
                arrival_code=destination,
                departure_time=travel_date + timedelta(hours=2), # Mock
                arrival_time=travel_date + timedelta(hours=6),   # Mock
                travel_class="DEFAULT",
                fare=valve.get('cost', 1000)
            )
            route.add_segment(segment)
            route.total_cost = valve.get('cost', 1000)
            route.metadata = {
                "mode": valve['mode'].upper(),
                "confidence": valve.get('confidence', 0.5),
                "is_verified": True,
                "ui_reasons": ["AI Recommended Alternative"]
            }
            results.append(route)

        # 3. If KG is dry and it's a high-priority request, trigger live discovery
        if not results:
            live_alts = await self._search_modal_alternative(source, destination, "bus")
            for alt in live_alts[:2]:
                route = Route()
                # Simplified conversion
                segment = RouteSegment(
                    train_number=alt.get('provider_id', 'BUS'),
                    train_name=f"Rapid {alt['transport_type'].capitalize()}",
                    departure_code=source,
                    arrival_code=destination,
                    departure_time=travel_date + timedelta(hours=4),
                    arrival_time=travel_date + timedelta(hours=9),
                    travel_class="AC",
                    fare=alt.get('total_cost', 800)
                )
                route.add_segment(segment)
                route.total_cost = alt.get('total_cost', 800)
                route.metadata = alt.get('metadata', {})
                route.metadata["mode"] = alt['transport_type'].upper()
                results.append(route)

        return results

arbitrage_agent = MultiModalArbitrageAgent()
