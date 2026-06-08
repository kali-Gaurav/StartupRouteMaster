"""
API Endpoints for Knowledge Graph Service

Provides REST API for:
- Knowledge graph queries and recommendations
- User preference management
- Route intelligence
- Market intelligence
- Metrics and health monitoring
"""

import logging
from typing import List, Dict, Any, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from enum import Enum

from services.knowledge_graph_service import (
    TravelKnowledgeGraph,
    UserPreference,
    get_knowledge_graph
)

logger = logging.getLogger("api.knowledge_graph")

router = APIRouter(prefix="/api/v1/knowledge-graph", tags=["Knowledge Graph"])


# ============================================================================
# Pydantic Models for API
# ============================================================================

class RouteQueryRequest(BaseModel):
    """Request model for route query"""
    source: str = Field(..., description="Source station code (e.g., NDLS)")
    destination: str = Field(..., description="Destination station code (e.g., BCT)")
    max_transfers: int = Field(2, description="Maximum number of transfers")


class RouteResponse(BaseModel):
    """Response model for route"""
    path: List[str]
    score: float
    segments: int
    details: List[Dict[str, Any]]


class RecommendationRequest(BaseModel):
    """Request model for personalized recommendations"""
    user_id: str
    source: Optional[str] = None
    destination: Optional[str] = None
    travel_date: Optional[str] = None


class RecommendationResponse(BaseModel):
    """Response model for recommendations"""
    type: str
    route: str = None
    confidence: float
    reason: str


class UserPreferenceRequest(BaseModel):
    """Request model for user preference creation/update"""
    user_id: str
    preferred_class: str = Field("SL", description="Preferred travel class")
    preferred_time_morning: bool = Field(False, description="Morning time preference")
    flexibility_score: float = Field(0.5, ge=0, le=1, description="Class flexibility")
    price_sensitivity: float = Field(0.5, ge=0, le=1, description="Price sensitivity")


class UserPreferenceResponse(BaseModel):
    """Response model for user preferences"""
    user_id: str
    preferred_stations: List[str]
    preferred_routes: List[str]
    preferred_times: List[int]
    preferred_time_morning: bool
    preferred_class: str
    class_flexibility: float
    avg_booking_advance_days: int
    cancellation_rate: float
    price_sensitivity: float


class RouteIntelligenceRequest(BaseModel):
    """Request model for route intelligence"""
    source: str
    destination: str


class RouteIntelligenceResponse(BaseModel):
    """Response model for route intelligence"""
    route: str
    optimal_paths: List[Dict[str, Any]]
    popularity: Dict[str, int]
    conversion_rate: float
    seasonal_patterns: Dict[str, Any]
    competitor_prices: Dict[str, Any]
    reliability_score: float


class SeasonalIntelligenceRequest(BaseModel):
    """Request model for seasonal intelligence"""
    source: str
    destination: str
    travel_month: int = Field(..., ge=1, le=12, description="Travel month (1-12)")


class SeasonalIntelligenceResponse(BaseModel):
    """Response model for seasonal intelligence"""
    month: str
    demand_score: float
    demand_level: str
    trend: str
    recommendation: str


class PriceIntelligenceRequest(BaseModel):
    """Request model for price intelligence"""
    source: str
    destination: str


class PriceIntelligenceResponse(BaseModel):
    """Response model for price intelligence"""
    status: str
    providers: int
    min_price: float
    max_price: float
    avg_price: float
    competitors: Dict[str, Any]


class GraphStatisticsResponse(BaseModel):
    """Response model for graph statistics"""
    total_stations: int
    total_routes: int
    total_edges: int
    total_interactions: int
    total_users: int
    tracked_routes: int
    avg_route_success: float
    last_update: str = None


class HealthResponse(BaseModel):
    """Response model for health check"""
    status: str
    circuit_breaker: Dict[str, Any]
    metrics: Dict[str, Any]
    last_update: str = None


class LearnFromBookingRequest(BaseModel):
    """Request model for learning from booking"""
    user_id: str
    source: str
    destination: str
    travel_date: str
    booking_date: str
    cancelled: bool = False
    booking_class: str = "SL"


class LearnFromSearchRequest(BaseModel):
    """Request model for learning from search"""
    user_id: Optional[str] = None
    source: str
    destination: str


# ============================================================================
# API Endpoints
# ============================================================================

@router.get("/health", response_model=HealthResponse)
async def health_check():
    """
    Health check endpoint for the knowledge graph service.
    """
    kg = get_knowledge_graph()
    return kg.health_check()


@router.get("/statistics", response_model=GraphStatisticsResponse)
async def get_graph_statistics():
    """
    Get knowledge graph statistics.
    """
    kg = get_knowledge_graph()
    stats = kg.get_graph_statistics()
    
    return GraphStatisticsResponse(
        total_stations=stats.get("total_stations", 0),
        total_routes=stats.get("total_routes", 0),
        total_edges=stats.get("total_edges", 0),
        total_interactions=stats.get("total_interactions", 0),
        total_users=stats.get("total_users", 0),
        tracked_routes=stats.get("tracked_routes", 0),
        avg_route_success=stats.get("avg_route_success", 0.0),
        last_update=stats.get("last_update")
    )


@router.post("/routes/query", response_model=List[RouteResponse])
async def query_optimal_routes(request: RouteQueryRequest):
    """
    Query the knowledge graph for optimal routes.
    
    Returns ranked routes based on learned knowledge including
    reliability, frequency, and popularity.
    """
    kg = get_knowledge_graph()
    
    try:
        routes = kg.query_optimal_routes(
            request.source,
            request.destination,
            request.max_transfers
        )
        
        return [
            RouteResponse(
                path=r["path"],
                score=r["score"],
                segments=r["segments"],
                details=r["details"]
            )
            for r in routes
        ]
    except Exception as e:
        logger.error(f"Error querying routes: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/recommendations", response_model=List[RecommendationResponse])
async def get_personalized_recommendations(request: RecommendationRequest):
    """
    Get personalized recommendations for a user.
    
    Uses collaborative filtering and learned preferences to generate
    relevant recommendations.
    """
    kg = get_knowledge_graph()
    
    try:
        # Build context
        context = {}
        if request.source:
            context["source"] = request.source
        if request.destination:
            context["destination"] = request.destination
        if request.travel_date:
            from datetime import datetime
            context["date"] = datetime.fromisoformat(request.travel_date)
        
        recommendations = await kg.get_personalized_recommendations(
            request.user_id,
            context
        )
        
        return [
            RecommendationResponse(
                type=r.get("type", "unknown"),
                route=r.get("route"),
                confidence=r.get("confidence", 0.0),
                reason=r.get("reason", "")
            )
            for r in recommendations
        ]
    except Exception as e:
        logger.error(f"Error getting recommendations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# User Preferences
# ============================================================================

@router.post("/preferences", response_model=UserPreferenceResponse)
async def create_or_update_preference(request: UserPreferenceRequest):
    """
    Create or update user preference profile.
    """
    kg = get_knowledge_graph()
    
    try:
        pref = kg.create_user_preference(
            user_id=request.user_id,
            preferred_class=request.preferred_class,
            preferred_time_morning=request.preferred_time_morning,
            flexibility_score=request.flexibility_score,
            price_sensitivity=request.price_sensitivity
        )
        
        return UserPreferenceResponse(
            user_id=pref.user_id,
            preferred_stations=pref.preferred_stations,
            preferred_routes=pref.preferred_routes,
            preferred_times=pref.preferred_times,
            preferred_time_morning=pref.preferred_time_morning,
            preferred_class=pref.preferred_class,
            class_flexibility=pref.class_flexibility,
            avg_booking_advance_days=pref.avg_booking_advance_days,
            cancellation_rate=pref.cancellation_rate,
            price_sensitivity=pref.price_sensitivity
        )
    except Exception as e:
        logger.error(f"Error creating preference: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/preferences/{user_id}", response_model=UserPreferenceResponse)
async def get_user_preference(user_id: str):
    """
    Get user preference profile.
    """
    kg = get_knowledge_graph()
    
    pref = kg.user_preferences.get(user_id)
    if not pref:
        raise HTTPException(status_code=404, detail=f"User {user_id} not found")
    
    return UserPreferenceResponse(
        user_id=pref.user_id,
        preferred_stations=pref.preferred_stations,
        preferred_routes=pref.preferred_routes,
        preferred_times=pref.preferred_times,
        preferred_time_morning=pref.preferred_time_morning,
        preferred_class=pref.preferred_class,
        class_flexibility=pref.class_flexibility,
        avg_booking_advance_days=pref.avg_booking_advance_days,
        cancellation_rate=pref.cancellation_rate,
        price_sensitivity=pref.price_sensitivity
    )


# ============================================================================
# Route Intelligence
# ============================================================================

@router.post("/intelligence/route", response_model=RouteIntelligenceResponse)
async def get_route_intelligence(request: RouteIntelligenceRequest):
    """
    Get comprehensive intelligence for a route.
    
    Includes popularity, conversion rates, seasonal patterns,
    and competitor pricing.
    """
    kg = get_knowledge_graph()
    
    try:
        intelligence = kg.get_route_intelligence(
            request.source,
            request.destination
        )
        
        return RouteIntelligenceResponse(
            route=intelligence.get("route", f"{request.source}->{request.destination}"),
            optimal_paths=intelligence.get("optimal_paths", []),
            popularity=intelligence.get("popularity", {}),
            conversion_rate=intelligence.get("conversion_rate", 0.0),
            seasonal_patterns=intelligence.get("seasonal_patterns", {}),
            competitor_prices=intelligence.get("competitor_prices", {}),
            reliability_score=intelligence.get("reliability_score", 0.85)
        )
    except Exception as e:
        logger.error(f"Error getting route intelligence: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/intelligence/seasonal", response_model=SeasonalIntelligenceResponse)
async def get_seasonal_intelligence(request: SeasonalIntelligenceRequest):
    """
    Get seasonal intelligence for a route.
    
    Returns demand prediction and recommendations for the travel month.
    """
    kg = get_knowledge_graph()
    
    try:
        intelligence = kg.get_seasonal_intelligence(
            f"{request.source}->{request.destination}",
            request.travel_month
        )
        
        return SeasonalIntelligenceResponse(
            month=intelligence.get("month", ""),
            demand_score=intelligence.get("demand_score", 0.5),
            demand_level=intelligence.get("demand_level", "medium"),
            trend=intelligence.get("trend", "unknown"),
            recommendation=intelligence.get("recommendation", "")
        )
    except Exception as e:
        logger.error(f"Error getting seasonal intelligence: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/intelligence/price", response_model=PriceIntelligenceResponse)
async def get_price_intelligence(request: PriceIntelligenceRequest):
    """
    Get price intelligence for a route.
    
    Returns competitor pricing information.
    """
    kg = get_knowledge_graph()
    
    try:
        route_key = f"{request.source}->{request.destination}"
        intelligence = kg.get_price_intelligence(route_key)
        
        return PriceIntelligenceResponse(
            status=intelligence.get("status", "no_data"),
            providers=intelligence.get("providers", 0),
            min_price=intelligence.get("min_price", 0.0),
            max_price=intelligence.get("max_price", 0.0),
            avg_price=intelligence.get("avg_price", 0.0),
            competitors=intelligence.get("competitors", {})
        )
    except Exception as e:
        logger.error(f"Error getting price intelligence: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Learning
# ============================================================================

@router.post("/learn/booking")
async def learn_from_booking(request: LearnFromBookingRequest):
    """
    Learn from a booking event.
    
    Updates user preferences and route patterns based on booking data.
    """
    kg = get_knowledge_graph()
    
    try:
        from datetime import datetime
        
        booking = {
            "user_id": request.user_id,
            "source": request.source,
            "destination": request.destination,
            "travel_date": datetime.fromisoformat(request.travel_date),
            "booking_date": datetime.fromisoformat(request.booking_date),
            "cancelled": request.cancelled,
            "booking_class": request.booking_class
        }
        
        await kg.learn_from_booking(booking)
        
        return {
            "status": "success",
            "message": "Learning from booking completed"
        }
    except Exception as e:
        logger.error(f"Error learning from booking: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/learn/search")
async def learn_from_search(request: LearnFromSearchRequest):
    """
    Learn from a search event.
    
    Updates route patterns based on search behavior.
    """
    kg = get_knowledge_graph()
    
    try:
        search = {
            "user_id": request.user_id,
            "source": request.source,
            "destination": request.destination
        }
        
        await kg.learn_from_search(search)
        
        return {
            "status": "success",
            "message": "Learning from search completed"
        }
    except Exception as e:
        logger.error(f"Error learning from search: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Market Intelligence
# ============================================================================

@router.post("/market/competitor-price")
async def update_competitor_price(
    route: str = Query(..., description="Route key (e.g., NDLS->BCT)"),
    provider: str = Query(..., description="Competitor name"),
    price: float = Query(..., description="Price offered by competitor")
):
    """
    Update competitor price for a route.
    """
    kg = get_knowledge_graph()
    
    try:
        kg.update_competitor_price(route, provider, price)
        
        return {
            "status": "success",
            "message": f"Updated {provider} price for {route}"
        }
    except Exception as e:
        logger.error(f"Error updating competitor price: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/market/seasonal-pattern")
async def update_seasonal_pattern(
    route: str = Query(..., description="Route key (e.g., NDLS->BCT)"),
    month: int = Query(..., ge=1, le=12, description="Month (1-12)"),
    demand_score: float = Query(..., ge=0, le=1, description="Demand score")
):
    """
    Update seasonal demand pattern for a route.
    """
    kg = get_knowledge_graph()
    
    try:
        kg.update_seasonal_pattern(route, month, demand_score)
        
        return {
            "status": "success",
            "message": f"Updated seasonal pattern for {route} in month {month}"
        }
    except Exception as e:
        logger.error(f"Error updating seasonal pattern: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# Persistence
# ============================================================================

@router.post("/persist")
async def persist_knowledge_graph():
    """
    Save knowledge graph state to database.
    """
    kg = get_knowledge_graph()
    
    try:
        success = await kg.save_to_database()
        
        if success:
            return {
                "status": "success",
                "message": "Knowledge graph saved to database"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to save knowledge graph")
    except Exception as e:
        logger.error(f"Error persisting knowledge graph: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/load")
async def load_knowledge_graph():
    """
    Load knowledge graph state from database.
    """
    kg = get_knowledge_graph()
    
    try:
        await kg.load_from_database()
        
        return {
            "status": "success",
            "message": "Knowledge graph loaded from database"
        }
    except Exception as e:
        logger.error(f"Error loading knowledge graph: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/reset-circuit-breaker")
async def reset_circuit_breaker():
    """
    Reset the circuit breaker for the knowledge graph service.
    """
    kg = get_knowledge_graph()
    kg.reset_circuit_breaker()
    
    return {
        "status": "success",
        "message": "Circuit breaker reset"
    }
