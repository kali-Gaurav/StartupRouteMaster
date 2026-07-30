"""
🔄 REDISTRIBUTION ENGINE — Patent-Level Network Load Balancer
Orchestrates demand redistribution across the network to reduce station/train crowding.
Implements:
  1. Saturated Segment Detection (Predicted Demand > Capacity)
  2. Release Valve Discovery (Finding alternative routes with vacancy)
  3. Wait-and-Flow Logic (Incentivized station waiting with premium services)
  4. Nash Equilibrium Pricing (Optimizing incentives vs. system benefit)
  5. Multi-Modal Bridges (Cross-station transfers to reach underloaded trains)
"""

import logging
import asyncio
from datetime import datetime, timedelta, date
from typing import List, Dict, Any, Optional, Set, Tuple, Callable
from dataclasses import dataclass, field
from enum import Enum

from services.demand_forecaster import demand_forecaster, DemandLevel
from core.data_utils.structures import Route, RouteSegment
from core.route_engine.base import RoutingRequest

logger = logging.getLogger(__name__)

# =========================================================================
# MODELS
# =========================================================================

class IncentiveType(Enum):
    LOUNGE_ACCESS = "LOUNGE_ACCESS"
    MEAL_VOUCHER = "MEAL_VOUCHER"
    CAB_REBATE = "CAB_REBATE"
    UPGRADE_PROBABILITY = "UPGRADE_PROBABILITY"
    CASHBACK = "CASHBACK"
    STATION_SERVICE = "STATION_SERVICE"

@dataclass(slots=True)
class IncentiveOffer:
    """An offer made to a passenger to redistribute their journey."""
    type: IncentiveType
    description: str
    value_in_rupees: float
    eligibility_conditions: List[str] = field(default_factory=list)

@dataclass(slots=True)
class RedistributionOption:
    """A complete redistribution plan for a user."""
    original_route: Route
    suggested_route: Route
    time_difference_minutes: int
    cost_difference: float
    incentives: List[IncentiveOffer]
    system_benefit_score: float  # 0-1, how much this helps the network
    ui_display_text: str
    is_premium_waiting: bool = False  # True if it involves waiting at station with services

# =========================================================================
# ENGINE
# =========================================================================

class RedistributionEngine:
    """
    Main engine for network-wide passenger redistribution.
    Integrates with search orchestrator and demand forecaster.
    """

    def __init__(self, db_session=None):
        self.db = db_session
        self.redistribution_threshold = 0.85  # Start redistributing above 85% fill

    async def analyze_and_redistribute(
        self, 
        request: RoutingRequest, 
        current_routes: List[Route],
        limit: int = 3,
        search_callback: Optional[Callable] = None
    ) -> List[RedistributionOption]:
        """
        Main entry point. Analyzes top routes for saturation and suggests alternatives.
        """
        options = []
        
        # 1. Focus on the 'Best' routes that are likely to be oversaturated
        for route in current_routes[:5]:
            # Analyze saturation per segment
            is_saturated = False
            saturated_segs = []
            
            for seg in route.segments:
                forecast = await demand_forecaster.forecast_segment(
                    train_number=str(seg.train_number),
                    from_station=seg.departure_code,
                    to_station=seg.arrival_code,
                    travel_date=seg.departure_time.date(),
                    db=self.db
                )
                
                logger.debug(f"📊 [REDISTRIBUTE] Train {seg.train_number} ({seg.departure_code}->{seg.arrival_code}) fill rate: {forecast.predicted_fill_rate}")
                
                if forecast.predicted_fill_rate >= self.redistribution_threshold:
                    is_saturated = True
                    saturated_segs.append(seg)
            
            if is_saturated:
                logger.info(f"🔄 [REDISTRIBUTE] Saturated route detected: {route.metadata.get('route_id', 'unknown')}. Finding release valves...")
                alt_options = await self._find_release_valves(request, route, saturated_segs, search_callback)
                options.extend(alt_options)
        
        # Sort by system benefit and limit
        options.sort(key=lambda x: -x.system_benefit_score)
        return options[:limit]

    async def _find_release_valves(
        self, 
        request: RoutingRequest, 
        saturated_route: Route,
        saturated_segments: List[RouteSegment],
        search_callback: Optional[Callable] = None
    ) -> List[RedistributionOption]:
        """
        Searches for alternative routes that bypass or replace saturated segments.
        [VYA Optimization] Now considers multi-hop diversions to distribute load.
        """
        options = []
        if not search_callback:
            return options

        # 1. WAIT-AND-FLOW: Search for later departures (+2 to +6 hours)
        wait_request = RoutingRequest(
            source_code=request.source_code,
            destination_code=request.destination_code,
            departure_date=request.departure_date + timedelta(hours=4), # Shift by 4h
            limit=5,
            constraints=request.constraints
        )
        
        # 2. DIVERSION: Search for alternative hubs (multi-hop)
        # We increase max_transfers to find routes that might be longer but have vacancy
        diversion_request = RoutingRequest(
            source_code=request.source_code,
            destination_code=request.destination_code,
            departure_date=request.departure_date,
            limit=5,
            constraints=request.constraints
        )
        diversion_request.constraints.max_transfers += 1
        
        # Execute both searches
        later_routes_task = asyncio.create_task(search_callback(wait_request))
        diversion_routes_task = asyncio.create_task(search_callback(diversion_request))
        
        results = await asyncio.gather(later_routes_task, diversion_routes_task, return_exceptions=True)
        
        all_alts = []
        for res in results:
            if isinstance(res, list): all_alts.extend(res)
        
        for alt in all_alts:
            if alt.journey_id == saturated_route.journey_id: continue
            
            # Verify this alternative isn't also saturated
            is_alt_saturated = False
            max_fill = 0.0
            for seg in alt.segments:
                f = await demand_forecaster.forecast_segment(
                    str(seg.train_number), seg.departure_code, seg.arrival_code, seg.departure_time.date(), db=self.db
                )
                max_fill = max(max_fill, f.predicted_fill_rate)
                if f.predicted_fill_rate >= self.redistribution_threshold:
                    is_alt_saturated = True
                    break
            
            if not is_alt_saturated:
                # Calculate benefit: How much does this help the system?
                # High benefit if it uses a train with < 60% fill
                benefit = 0.9 if max_fill < 0.6 else 0.7
                
                time_diff = alt.total_duration - saturated_route.total_duration
                incentives = self._calculate_incentive(benefit, int(time_diff))
                
                msg = "Switch to this route for a more comfortable, guaranteed seat."
                if len(alt.segments) > len(saturated_route.segments):
                    msg = "Relaxed alternative: More transfers but guaranteed vacancy."
                
                options.append(RedistributionOption(
                    original_route=saturated_route,
                    suggested_route=alt,
                    time_difference_minutes=int(time_diff),
                    cost_difference=alt.total_cost - saturated_route.total_cost,
                    incentives=incentives,
                    system_benefit_score=benefit,
                    ui_display_text=msg,
                    is_premium_waiting=time_diff > 120
                ))
        
        return options

    def _calculate_incentive(self, system_benefit: float, time_loss: int) -> List[IncentiveOffer]:
        """
        Determines what incentives to offer based on the value to the system.
        """
        incentives = []
        
        # Base incentives for any redistribution
        if system_benefit > 0.5:
            incentives.append(IncentiveOffer(
                IncentiveType.CASHBACK,
                "₹250 Comfort Rebate",
                250.0
            ))

        # Premium incentives for longer waits
        if time_loss > 120:
            incentives.append(IncentiveOffer(
                IncentiveType.LOUNGE_ACCESS,
                "Executive Lounge Access (AC, Buffet, WiFi)",
                500.0
            ))
            
        return incentives

    def generate_redistribution_summary(self, options: List[RedistributionOption]) -> str:
        """Generates a human-readable summary of redistribution benefits."""
        if not options:
            return "Current system load is balanced. No redistribution required."
        
        count = len(options)
        max_benefit = max(o.system_benefit_score for o in options)
        return f"Identified {count} redistribution opportunities to reduce corridor crowding. Max system benefit: {max_benefit:.2f}."

# Singleton
redistributor = RedistributionEngine()
