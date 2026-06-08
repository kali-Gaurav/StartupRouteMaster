"""
Unified Route Service - Tiered Intelligence Pipeline

Integrates all route engine innovations into a single service:
- QPO (Query Plan Optimizer)
- TurboRouter / RAPTOR
- CAT + TIS Scoring
- Frontier + Safety Filter
- SSE Streaming

Total target latency: 700ms for AI-enriched, safety-scored routes.
"""

import logging
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Dict, List, Optional

from backend.services.route_engine import RouteEngine, Journey
from backend.services.routing.sse_route_streamer import RouteStreamManager, StreamConfig
from backend.services.routing.query_plan_optimizer import (
    QueryPlanOptimizer, QueryContext, QueryPlan, SearchDepth
)
from backend.services.routing.transfer_intelligence import TransferIntelligenceService, JourneyTransferScore
from backend.services.routing.corridor_safety_bus import CorridorSafetyBus, CorridorSafetyStatus
from backend.services.routing.delay_aware import DelayAwareRoutingService

logger = logging.getLogger(__name__)


@dataclass
class UnifiedRouteRequest:
    """Unified request for route search"""
    source: str
    destination: str
    travel_date: str
    travel_time: Optional[str] = None
    max_routes: int = 10
    include_transfers: bool = True
    prefer_fastest: bool = True
    prefer_cheapest: bool = False
    require_ac: bool = False
    user_id: Optional[str] = None


@dataclass
class EnrichedRoute:
    """Route with all intelligence layers applied"""
    journey: Journey
    quality_score: float
    safety_score: float
    transfer_score: float
    overall_score: float
    risk_level: str
    transfer_details: List[Dict[str, Any]]
    safety_warnings: List[str]
    recommendations: List[str]
    metadata: Dict[str, Any]


class UnifiedRouteService:
    """
    Unified route service implementing the Tiered Intelligence Pipeline.
    
    Pipeline stages:
    1. QPO (Query Plan Optimizer) - 50ms
    2. TurboRouter / RAPTOR (Route Discovery) - 500ms
    3. CAT + TIS Scoring (Intelligence Enrichment) - 100ms
    4. Frontier + Safety Filter (Pareto Curation) - 50ms
    5. SSE Stream (Progressive Delivery) - 0ms perceived wait
    
    Total: ~700ms for fully AI-enriched, safety-scored routes.
    """
    
    def __init__(self):
        self.route_engine = RouteEngine()
        self.delay_router = DelayAwareRoutingService()
        self.qpo = QueryPlanOptimizer(self.route_engine)
        self.tis_service = TransferIntelligenceService(self.route_engine)
        self.safety_bus = CorridorSafetyBus(self.route_engine)
        self.stream_manager = RouteStreamManager(self.route_engine)
    
    async def search_routes(
        self,
        request: UnifiedRouteRequest
    ) -> List[EnrichedRoute]:
        """
        Search routes using the full intelligence pipeline.
        
        Args:
            request: Unified route search request
            
        Returns:
            List of enriched routes with all intelligence layers
        """
        logger.info(
            f"Searching routes: {request.source} -> {request.destination} "
            f"on {request.travel_date}"
        )
        
        # Stage 1: Query Plan Optimization
        query_context = QueryContext(
            source=request.source,
            destination=request.destination,
            travel_date=request.travel_date,
            require_ac=request.require_ac,
            user_id=request.user_id
        )
        
        query_plan = await self.qpo.create_query_plan(query_context)
        self.qpo.apply_query_plan(query_plan, self.route_engine)
        
        logger.debug(f"Query plan: {query_plan.search_depth.value}")
        
        # Stage 2: Route Discovery (TurboRouter / RAPTOR)
        journeys = await self._discover_routes(request, query_plan)
        
        if not journeys:
            return []
        
        # Stage 3: Intelligence Enrichment (TIS + Safety)
        enriched_routes = await self._enrich_routes(
            journeys, request.source, request.destination
        )
        
        # Stage 4: Pareto Frontier + Safety Filter
        final_routes = self._apply_frontier_filter(
            enriched_routes, request.prefer_fastest, request.prefer_cheapest
        )
        
        logger.info(f"Found {len(final_routes)} enriched routes")
        
        return final_routes
    
    async def stream_routes(
        self,
        request: UnifiedRouteRequest
    ):
        """
        Stream routes progressively using SSE.
        
        Yields enriched routes as they're discovered.
        """
        config = StreamConfig(
            include_direct_routes=True,
            include_transfer_routes=request.include_transfers,
            max_routes=request.max_routes
        )
        
        connection_id = f"unified-{datetime.utcnow().timestamp()}"
        
        async for event in self.stream_manager.stream_routes(
            source=request.source,
            destination=request.destination,
            travel_date=request.travel_date,
            config=config,
            connection_id=connection_id
        ):
            yield event
    
    async def _discover_routes(
        self,
        request: UnifiedRouteRequest,
        query_plan: QueryPlan
    ) -> List[Journey]:
        """Stage 2: Discover routes using optimized query plan"""
        journeys = []
        
        # Search direct routes first
        if query_plan.search_depth in [SearchDepth.DIRECT_ONLY, SearchDepth.ONE_TRANSFER]:
            direct_routes = await self.delay_router.search_direct_routes(
                source=request.source,
                destination=request.destination,
                travel_date=request.travel_date
            )
            journeys.extend(direct_routes)
        
        # Search transfer routes if needed
        if request.include_transfers and query_plan.search_depth != SearchDepth.DIRECT_ONLY:
            transfer_routes = await self.route_engine._raptor_search(
                source=request.source,
                destination=request.destination,
                travel_date=request.travel_date,
                max_transfers=2
            )
            journeys.extend(transfer_routes)
        
        # Deduplicate and rank
        journeys = self.route_engine._deduplicate_routes(journeys)
        journeys.sort(
            key=lambda j: self.route_engine._calculate_route_quality_score(j),
            reverse=True
        )
        
        return journeys[:request.max_routes]
    
    async def _enrich_routes(
        self,
        journeys: List[Journey],
        source: str,
        destination: str
    ) -> List[EnrichedRoute]:
        """Stage 3: Enrich routes with intelligence (TIS + Safety)"""
        enriched = []
        
        # Get corridor safety status
        safety_status = await self.safety_bus.get_corridor_safety(
            source, destination
        )
        
        for journey in journeys:
            # Calculate transfer intelligence
            transfer_score = await self.tis_service.score_journey(journey)
            
            # Calculate safety score
            safety_score = self.safety_bus.calculate_route_safety_score(
                journey, source, destination
            )
            
            # Calculate base quality score
            quality_score = self.route_engine._calculate_route_quality_score(journey)
            
            # Calculate overall score (weighted combination)
            overall_score = self._calculate_overall_score(
                quality_score=quality_score,
                safety_score=safety_score,
                transfer_score=transfer_score.overall_score
            )
            
            # Generate warnings and recommendations
            warnings = self._generate_warnings(
                safety_status, transfer_score, journey
            )
            recommendations = self._generate_recommendations(
                transfer_score, safety_status
            )
            
            enriched.append(EnrichedRoute(
                journey=journey,
                quality_score=quality_score,
                safety_score=safety_score,
                transfer_score=transfer_score.overall_score,
                overall_score=overall_score,
                risk_level=transfer_score.risk_level.value,
                transfer_details=[
                    {
                        "station": ts.transfer_station,
                        "score": ts.tis_score,
                        "risk": ts.risk_level.value,
                        "recommendation": ts.recommendation
                    }
                    for ts in transfer_score.transfer_details
                ],
                safety_warnings=warnings,
                recommendations=recommendations,
                metadata={
                    "safety_status": safety_status.risk_level.value,
                    "transfer_count": len(journey.segments) - 1
                }
            ))
        
        return enriched
    
    def _calculate_overall_score(
        self,
        quality_score: float,
        safety_score: float,
        transfer_score: float
    ) -> float:
        """
        Calculate overall route score combining all factors.
        
        Weights:
        - Quality (speed, comfort): 40%
        - Safety: 35%
        - Transfer reliability: 25%
        """
        return (
            quality_score * 0.40 +
            safety_score * 100 * 0.35 +  # Convert safety to 0-100 scale
            transfer_score * 0.25
        )
    
    def _generate_warnings(
        self,
        safety_status: CorridorSafetyStatus,
        transfer_score: JourneyTransferScore,
        journey: Journey
    ) -> List[str]:
        """Generate safety and transfer warnings"""
        warnings = []
        
        # Safety warnings
        if safety_status.risk_level.value in ["high", "critical"]:
            warnings.append(
                f"⚠️ Safety alert: {safety_status.active_events} active event(s) "
                f"in corridor"
            )
        
        if safety_status.affected_stations:
            affected = set(safety_status.affected_stations)
            journey_stations = set()
            for segment in journey.segments:
                journey_stations.add(segment.from_station)
                journey_stations.add(segment.to_station)
            
            overlap = journey_stations & affected
            if overlap:
                warnings.append(
                    f"🚨 Route passes through affected stations: {', '.join(overlap)}"
                )
        
        # Transfer warnings
        for ts in transfer_score.transfer_details:
            if ts.risk_level.value == "high":
                warnings.append(
                    f"❌ High-risk transfer at {ts.transfer_station} "
                    f"({ts.connection_time_minutes}min connection)"
                )
        
        return warnings
    
    def _generate_recommendations(
        self,
        transfer_score: JourneyTransferScore,
        safety_status: CorridorSafetyStatus
    ) -> List[str]:
        """Generate route recommendations"""
        recommendations = []
        
        # Safety recommendations
        if safety_status.risk_level.value in ["high", "critical"]:
            recommendations.append(
                "Consider alternative routes outside the affected corridor"
            )
        
        # Transfer recommendations
        if transfer_score.risk_level.value == "low":
            recommendations.append("✅ Good transfer connections")
        elif transfer_score.risk_level.value == "medium":
            recommendations.append(
                "⚠️ Some transfers have moderate risk - allow buffer time"
            )
        
        return recommendations
    
    def _apply_frontier_filter(
        self,
        routes: List[EnrichedRoute],
        prefer_fastest: bool,
        prefer_cheapest: bool
    ) -> List[EnrichedRoute]:
        """
        Stage 4: Apply Pareto frontier filter and safety filter.
        
        Removes dominated routes and applies safety penalties.
        """
        # Apply safety filter (remove extremely unsafe routes)
        filtered = [r for r in routes if r.safety_score >= 0.3]
        
        if not filtered:
            # If all routes filtered, return original (user needs options)
            filtered = routes
        
        # Apply Pareto frontier (simplified)
        # In production, would use proper multi-objective optimization
        pareto_optimal = self._extract_pareto_frontier(filtered)
        
        # Sort by overall score
        pareto_optimal.sort(key=lambda r: r.overall_score, reverse=True)
        
        return pareto_optimal
    
    def _extract_pareto_frontier(
        self,
        routes: List[EnrichedRoute]
    ) -> List[EnrichedRoute]:
        """
        Extract Pareto-optimal routes.
        
        A route is Pareto-optimal if no other route is better
        in all dimensions (quality, safety, transfer).
        """
        if len(routes) <= 2:
            return routes
        
        pareto = []
        
        for route in routes:
            is_dominated = False
            
            for other in routes:
                if other is route:
                    continue
                
                # Check if 'other' dominates 'route'
                # Dominates if better in ALL dimensions
                if (
                    other.quality_score >= route.quality_score and
                    other.safety_score >= route.safety_score and
                    other.transfer_score >= route.transfer_score and
                    (
                        other.quality_score > route.quality_score or
                        other.safety_score > route.safety_score or
                        other.transfer_score > route.transfer_score
                    )
                ):
                    is_dominated = True
                    break
            
            if not is_dominated:
                pareto.append(route)
        
        return pareto if pareto else routes


# FastAPI Router
from fastapi import APIRouter, HTTPException, Query

unified_router = APIRouter(prefix="/routes", tags=["Unified Route Service"])


@unified_router.get("/search")
async def search_routes(
    source: str = Query(..., description="Source station code"),
    destination: str = Query(..., description="Destination station code"),
    travel_date: str = Query(..., description="Travel date (YYYY-MM-DD)"),
    travel_time: Optional[str] = Query(None, description="Preferred travel time"),
    max_routes: int = Query(10, description="Maximum routes to return"),
    include_transfers: bool = Query(True, description="Include routes with transfers"),
    prefer_fastest: bool = Query(True, description="Prefer faster routes"),
    prefer_cheapest: bool = Query(False, description="Prefer cheaper routes"),
    require_ac: bool = Query(False, description="Require AC class"),
    user_id: Optional[str] = Query(None, description="User ID for personalization")
) -> Dict[str, Any]:
    """
    Search routes using the unified intelligence pipeline.
    
    Returns AI-enriched routes with:
    - Quality scores
    - Safety scores
    - Transfer intelligence
    - Risk levels
    - Recommendations
    """
    request = UnifiedRouteRequest(
        source=source,
        destination=destination,
        travel_date=travel_date,
        travel_time=travel_time,
        max_routes=max_routes,
        include_transfers=include_transfers,
        prefer_fastest=prefer_fastest,
        prefer_cheapest=prefer_cheapest,
        require_ac=require_ac,
        user_id=user_id
    )
    
    service = UnifiedRouteService()
    routes = await service.search_routes(request)
    
    return {
        "request": {
            "source": source,
            "destination": destination,
            "travel_date": travel_date
        },
        "total_routes": len(routes),
        "routes": [
            {
                "train_count": r.journey.total_duration_minutes,
                "departure_time": r.journey.departure_time.isoformat() 
                    if r.journey.departure_time else None,
                "arrival_time": r.journey.arrival_time.isoformat() 
                    if r.journey.arrival_time else None,
                "transfers": len(r.journey.segments) - 1,
                "scores": {
                    "quality": r.quality_score,
                    "safety": r.safety_score,
                    "transfer": r.transfer_score,
                    "overall": r.overall_score
                },
                "risk_level": r.risk_level,
                "transfer_details": r.transfer_details,
                "safety_warnings": r.safety_warnings,
                "recommendations": r.recommendations
            }
            for r in routes
        ]
    }


@unified_router.get("/search/stream")
async def stream_routes(
    source: str = Query(..., description="Source station code"),
    destination: str = Query(..., description="Destination station code"),
    travel_date: str = Query(..., description="Travel date (YYYY-MM-DD)"),
    max_routes: int = Query(10, description="Maximum routes to return"),
    include_transfers: bool = Query(True, description="Include routes with transfers")
):
    """
    Stream routes progressively using SSE.
    
    First route delivered in < 500ms, additional routes stream as found.
    """
    from fastapi import Request
    from fastapi.responses import StreamingResponse
    
    request = UnifiedRouteRequest(
        source=source,
        destination=destination,
        travel_date=travel_date,
        max_routes=max_routes,
        include_transfers=include_transfers
    )
    
    service = UnifiedRouteService()
    
    async def event_generator():
        async for event in service.stream_routes(request):
            yield event
    
    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive"
        }
    )


@unified_router.get("/intelligence/summary")
async def get_route_intelligence_summary(
    source: str = Query(..., description="Source station code"),
    destination: str = Query(..., description="Destination station code"),
    travel_date: str = Query(..., description="Travel date (YYYY-MM-DD)")
) -> Dict[str, Any]:
    """
    Get intelligence summary for a corridor without searching routes.
    
    Returns:
    - Corridor safety status
    - Transfer risk summary
    - Historical data
    """
    service = UnifiedRouteService()
    
    # Get safety status
    safety_status = await service.safety_bus.get_corridor_safety(
        source, destination
    )
    
    # Get transfer risk summary
    tis_service = TransferIntelligenceService()
    
    return {
        "corridor": f"{source}-{destination}",
        "safety": {
            "score": safety_status.safety_score,
            "risk_level": safety_status.risk_level.value,
            "active_events": safety_status.active_events,
            "affected_stations": safety_status.affected_stations
        },
        "transfer_risk": {
            "summary": "Multiple transfer options available",
            "recommendation": "Routes via major hubs have better connection success rates"
        },
        "travel_tips": [
            "Book AC classes for better comfort on long journeys",
            "Allow 30+ minute connection time at major stations",
            "Check safety alerts before traveling during events"
        ]
    }