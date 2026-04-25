"""
API Endpoints for Demand Redistribution Service

Provides REST API for:
- Network demand analysis
- Redistribution opportunity identification
- Passenger offer generation and management
- Metrics and health monitoring
"""

import logging
from typing import List, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field

from services.demand_redistribution_service import (
    DemandRedistributionService,
    DemandSnapshot,
    RedistributionOpportunity,
    PassengerOffer,
    get_redistribution_service
)
from database.session import SessionLocal

logger = logging.getLogger("api.redistribution")

router = APIRouter(prefix="/api/v1/redistribution", tags=["Demand Redistribution"])


# ============================================================================
# Pydantic Models for API
# ============================================================================

class DemandSnapshotResponse(BaseModel):
    """Response model for demand snapshot"""
    route_id: str
    source: str
    destination: str
    travel_date: str
    total_capacity: int
    current_bookings: int
    search_demand: int
    demand_score: float
    available_seats: int
    occupancy_rate: float


class RedistributionOpportunityResponse(BaseModel):
    """Response model for redistribution opportunity"""
    source_route: DemandSnapshotResponse
    target_route: DemandSnapshotResponse
    passengers_needed: int
    incentive_min: float
    incentive_max: float
    time_advantage: int


class PassengerOfferResponse(BaseModel):
    """Response model for passenger offer"""
    passenger_id: str
    original_route: Dict[str, Any]
    alternative_route: Dict[str, Any]
    incentive_amount: float
    time_difference_minutes: int
    comfort_improvement: float
    message: str
    expires_at: str
    utility_score: float


class OfferResponseRequest(BaseModel):
    """Request model for passenger offer response"""
    passenger_id: str
    accepted: bool = Field(..., description="Whether the passenger accepted the offer")


class NetworkSummaryResponse(BaseModel):
    """Response model for network summary"""
    total_routes: int
    high_demand_routes: int
    low_demand_routes: int
    balanced_routes: int
    last_analysis: str = None
    active_offers: int


class MetricsResponse(BaseModel):
    """Response model for service metrics"""
    total_operations: int
    successful_operations: int
    failed_operations: int
    success_rate: float
    avg_incentive: float
    active_offers: int
    acceptance_rates: Dict[str, float]
    circuit_breaker_state: str


class HealthResponse(BaseModel):
    """Response model for health check"""
    status: str
    circuit_breaker: Dict[str, Any]
    metrics: Dict[str, Any]
    last_analysis: str = None


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint for the redistribution service.
    """
    service = get_redistribution_service()
    return service.health_check()


@router.get("/metrics", response_model=MetricsResponse)
async def get_metrics():
    """
    Get service metrics and performance statistics.
    """
    service = get_redistribution_service()
    metrics = service.get_metrics()
    
    return MetricsResponse(
        total_operations=metrics.get("total_operations", 0),
        successful_operations=metrics.get("successful_operations", 0),
        failed_operations=metrics.get("failed_operations", 0),
        success_rate=metrics.get("success_rate", 0.0),
        avg_incentive=metrics.get("avg_incentive", 0.0),
        active_offers=metrics.get("active_offers", 0),
        acceptance_rates=metrics.get("acceptance_rates", {}),
        circuit_breaker_state=metrics.get("circuit_breaker_state", "closed")
    )


@router.post("/analyze", response_model=Dict[str, Any])
async def analyze_network_demand():
    """
    Trigger network demand analysis.
    
    This analyzes current demand across all active routes and returns
    demand snapshots for each route.
    """
    service = get_redistribution_service()
    
    try:
        snapshots = await service.analyze_network_demand()
        
        return {
            "status": "success",
            "routes_analyzed": len(snapshots),
            "snapshots": [
                {
                    "route_id": s.route_id,
                    "source": s.source,
                    "destination": s.destination,
                    "travel_date": s.travel_date.isoformat() if s.travel_date else None,
                    "total_capacity": s.total_capacity,
                    "current_bookings": s.current_bookings,
                    "search_demand": s.search_demand,
                    "demand_score": s.demand_score,
                    "available_seats": s.available_seats,
                    "occupancy_rate": s.occupancy_rate
                }
                for s in snapshots.values()
            ],
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error analyzing network demand: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary", response_model=NetworkSummaryResponse)
async def get_network_summary():
    """
    Get summary of current network demand.
    
    Returns counts of high-demand, low-demand, and balanced routes.
    """
    service = get_redistribution_service()
    summary = service.get_network_summary()
    
    if summary.get("status") == "no_data":
        return NetworkSummaryResponse(
            total_routes=0,
            high_demand_routes=0,
            low_demand_routes=0,
            balanced_routes=0,
            active_offers=0
        )
    
    return NetworkSummaryResponse(
        total_routes=summary.get("total_routes", 0),
        high_demand_routes=summary.get("high_demand_routes", 0),
        low_demand_routes=summary.get("low_demand_routes", 0),
        balanced_routes=summary.get("balanced_routes", 0),
        last_analysis=summary.get("last_analysis"),
        active_offers=summary.get("active_offers", 0)
    )


@router.get("/opportunities", response_model=List[RedistributionOpportunityResponse])
async def identify_opportunities(
    min_passengers: int = Query(5, description="Minimum passengers needed"),
    max_results: int = Query(10, description="Maximum opportunities to return")
):
    """
    Identify redistribution opportunities.
    
    Returns routes that can benefit from passenger redistribution,
    sorted by potential impact.
    """
    service = get_redistribution_service()
    
    try:
        opportunities = await service.identify_opportunities()
        
        # Filter by minimum passengers
        opportunities = [o for o in opportunities if o.passengers_needed >= min_passengers]
        
        # Limit results
        opportunities = opportunities[:max_results]
        
        return [
            RedistributionOpportunityResponse(
                source_route=DemandSnapshotResponse(
                    route_id=o.source_route.route_id,
                    source=o.source_route.source,
                    destination=o.source_route.destination,
                    travel_date=o.source_route.travel_date.isoformat() if o.source_route.travel_date else None,
                    total_capacity=o.source_route.total_capacity,
                    current_bookings=o.source_route.current_bookings,
                    search_demand=o.source_route.search_demand,
                    demand_score=o.source_route.demand_score,
                    available_seats=o.source_route.available_seats,
                    occupancy_rate=o.source_route.occupancy_rate
                ),
                target_route=DemandSnapshotResponse(
                    route_id=o.target_route.route_id,
                    source=o.target_route.source,
                    destination=o.target_route.destination,
                    travel_date=o.target_route.travel_date.isoformat() if o.target_route.travel_date else None,
                    total_capacity=o.target_route.total_capacity,
                    current_bookings=o.target_route.current_bookings,
                    search_demand=o.target_route.search_demand,
                    demand_score=o.target_route.demand_score,
                    available_seats=o.target_route.available_seats,
                    occupancy_rate=o.target_route.occupancy_rate
                ),
                passengers_needed=o.passengers_needed,
                incentive_min=o.incentive_range[0],
                incentive_max=o.incentive_range[1],
                time_advantage=o.time_advantage
            )
            for o in opportunities
        ]
    except Exception as e:
        logger.error(f"Error identifying opportunities: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/offers/generate", response_model=List[PassengerOfferResponse])
async def generate_offers(
    source_route: str = Query(..., description="Source route ID"),
    target_route: str = Query(..., description="Target route ID"),
    limit: int = Query(10, description="Maximum offers to generate")
):
    """
    Generate passenger offers for a specific redistribution opportunity.
    
    Requires source_route and target_route parameters to identify the opportunity.
    """
    service = get_redistribution_service()
    
    try:
        # First analyze network to get snapshots
        await service.analyze_network_demand()
        
        # Find the specific opportunity
        opportunities = await service.identify_opportunities()
        opportunity = None
        
        for o in opportunities:
            if o.source_route.route_id == source_route and o.target_route.route_id == target_route:
                opportunity = o
                break
        
        if not opportunity:
            raise HTTPException(
                status_code=404, 
                detail=f"No opportunity found between {source_route} and {target_route}"
            )
        
        # Generate offers
        offers = await service.generate_passenger_offers(opportunity, limit)
        
        return [
            PassengerOfferResponse(
                passenger_id=o.passenger_id,
                original_route={
                    "route_id": o.original_route.route_id,
                    "source": o.original_route.source,
                    "destination": o.original_route.destination
                },
                alternative_route={
                    "route_id": o.alternative_route.route_id,
                    "source": o.alternative_route.source,
                    "destination": o.alternative_route.destination
                },
                incentive_amount=o.incentive_amount,
                time_difference_minutes=o.time_difference_minutes,
                comfort_improvement=o.comfort_improvement,
                message=o.message,
                expires_at=o.expires_at.isoformat(),
                utility_score=o.utility_score
            )
            for o in offers
        ]
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error generating offers: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/offers/respond")
async def respond_to_offer(request: OfferResponseRequest):
    """
    Process passenger response to a redistribution offer.
    
    Records whether the passenger accepted or declined the offer.
    """
    service = get_redistribution_service()
    
    try:
        result = await service.process_offer_response(
            request.passenger_id,
            request.accepted
        )
        
        return result
    except Exception as e:
        logger.error(f"Error processing offer response: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/execute")
async def execute_redistribution(
    passenger_ids: List[str] = Query(..., description="List of passenger IDs who accepted")
):
    """
    Execute redistribution for accepted offers.
    
    Takes a list of passenger IDs who have accepted redistribution offers
    and processes the actual booking changes.
    """
    service = get_redistribution_service()
    
    try:
        # Get active offers for these passengers
        offers = []
        for pid in passenger_ids:
            if pid in service._active_offers:
                offers.append(service._active_offers[pid])
        
        if not offers:
            return {
                "status": "warning",
                "message": "No active offers found for provided passenger IDs",
                "processed": 0
            }
        
        # Execute redistribution
        result = await service.execute_redistribution(offers)
        
        return {
            "status": "success",
            "result": result,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"Error executing redistribution: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset-circuit-breaker")
async def reset_circuit_breaker():
    """
    Reset the circuit breaker for the redistribution service.
    
    Use this when the service has recovered from failures.
    """
    service = get_redistribution_service()
    service.reset_circuit_breaker()
    
    return {
        "status": "success",
        "message": "Circuit breaker reset"
    }