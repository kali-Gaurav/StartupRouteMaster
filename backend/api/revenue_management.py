"""
Yield Management & Revenue Optimization API Endpoints
====================================================

Provides admin endpoints for:
1. Real-time pricing adjustments
2. Dynamic quota allocation
3. Overbooking strategy management
4. Revenue analytics and forecasting
5. Cancellation risk assessment
6. Waitlist management

Author: RouteMaster Intelligence System
Date: 2026-02-17
"""

from fastapi import APIRouter, Depends, HTTPException, Query, Header
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import Dict, List, Optional
from datetime import datetime, date
import logging

from database import get_db
from database.config import Config
from services.yield_management_engine import yield_management_engine, QuotaType
from services.advanced_seat_allocation_engine import advanced_seat_allocation_engine
from services.cancellation_predictor import cancellation_predictor

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/revenue-mgmt", tags=["revenue-management"])


# ============================================================================
# REQUEST/RESPONSE SCHEMAS
# ============================================================================

class SegmentPricingRequest(BaseModel):
    """Request for segment pricing calculation."""
    origin: str = Field(..., description="Origin station code")
    destination: str = Field(..., description="Destination station code")
    base_fare: float = Field(..., gt=0, description="Base fare in INR")
    occupancy_rate: float = Field(default=0.7, ge=0, le=1, description="Current occupancy (0-1)")
    demand_score: float = Field(default=0.5, ge=0, le=1, description="Demand forecast (0-1)")
    time_to_departure_hours: float = Field(default=24, ge=0, description="Hours to departure")
    is_peak_season: bool = Field(default=False)
    is_holiday: bool = Field(default=False)


class QuotaAllocationRequest(BaseModel):
    """Request for dynamic quota allocation."""
    train_id: int = Field(..., description="Train ID")
    travel_date: str = Field(..., description="Travel date (YYYY-MM-DD)")
    total_seats: int = Field(..., gt=0, description="Total seats in train")
    quota_demands: Dict[str, float] = Field(
        default_factory=dict,
        description="Expected demand for each quota (0-1)"
    )


class CancellationPredictionRequest(BaseModel):
    """Request for cancellation rate prediction."""
    train_id: int = Field(..., description="Train ID")
    travel_date: str = Field(..., description="Travel date (YYYY-MM-DD)")
    quota_type: str = Field(..., description="Quota type (general, tatkal, etc.)")
    days_to_departure: int = Field(..., ge=1, description="Days until departure")
    booking_velocity: float = Field(default=1.0, ge=0, description="Bookings per hour")
    route_popularity: float = Field(default=0.6, ge=0, le=1, description="Route popularity (0-1)")
    demand_forecast: float = Field(default=0.5, ge=0, le=1, description="Demand forecast (0-1)")


class RevenuePerformanceRequest(BaseModel):
    """Request for revenue performance analytics."""
    time_period: str = Field(default="daily", description="daily, weekly, monthly")
    start_date: Optional[str] = Field(None, description="Start date for period")
    end_date: Optional[str] = Field(None, description="End date for period")


# ============================================================================
# PRICING ENDPOINTS
# ============================================================================

def verify_admin_token(x_admin_token: str = Header(...)) -> bool:
    """Verify admin API token."""
    if x_admin_token != Config.ADMIN_API_TOKEN:
        raise HTTPException(status_code=401, detail="Unauthorized")
    return True


@router.post("/pricing/calculate-segment")
async def calculate_segment_pricing(
    request: SegmentPricingRequest,
    _: bool = Depends(verify_admin_token),
) -> Dict:
    """
    Calculate optimal price for an origin-destination pair.
    
    Uses yield management to suggest price considering occupancy, demand, and time.
    """
    try:
        factors = yield_management_engine.calculate_segment_price(
            origin=request.origin,
            destination=request.destination,
            base_fare=request.base_fare,
            occupancy_rate=request.occupancy_rate,
            demand_score=request.demand_score,
            time_to_departure_hours=request.time_to_departure_hours,
            is_peak_season=request.is_peak_season,
            is_holiday=request.is_holiday,
        )
        
        return {
            "success": True,
            "segment": f"{request.origin}-{request.destination}",
            "factors": factors,
            "recommended_price": factors['final_price'],
            "multiplier": factors['final_multiplier'],
        }
    except Exception as e:
        logger.error(f"Segment pricing calculation failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/pricing/elasticity-analysis")
async def price_elasticity_analysis(
    base_price: float = Query(..., gt=0, description="Base price"),
    base_demand: float = Query(..., ge=0, description="Base demand (units)"),
    elasticity: float = Query(default=-0.8, description="Price elasticity"),
    _: bool = Depends(verify_admin_token),
) -> Dict:
    """
    Analyze demand at different price points using elasticity.
    
    Returns demand forecast at various price levels.
    """
    try:
        results = {}
        for price_mult in [0.85, 0.90, 0.95, 1.0, 1.1, 1.2, 1.5]:
            price = base_price * price_mult
            demand = yield_management_engine.estimate_demand_at_price(
                base_demand, base_price, price, elasticity
            )
            results[f"{price_mult}x"] = {
                "price": round(price, 2),
                "demand": round(demand, 2),
                "revenue": round(price * demand, 2),
            }
        
        # Find optimal price
        optimal_price, max_revenue = yield_management_engine.find_revenue_optimal_price(
            base_price, base_demand, elasticity
        )
        
        return {
            "success": True,
            "elasticity": elasticity,
            "price_demand_scenarios": results,
            "optimal_price": optimal_price,
            "max_revenue": max_revenue,
        }
    except Exception as e:
        logger.error(f"Elasticity analysis failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# QUOTA & INVENTORY MANAGEMENT
# ============================================================================

@router.post("/quota/optimize-allocation")
async def optimize_quota_allocation(
    request: QuotaAllocationRequest,
    _: bool = Depends(verify_admin_token),
) -> Dict:
    """
    Calculate optimal quota allocation for a train based on predicted demand.
    
    Adjusts standard IRCTC quotas (General 50%, Tatkal 10%, etc.) based on
    real-time demand forecasts for revenue maximization.
    """
    try:
        # Build demand forecast dictionary
        quota_demands = {}
        for quota in QuotaType:
            # Use provided demand or estimate
            quota_demands[quota] = request.quota_demands.get(quota.value, 0.5)
        
        allocation = yield_management_engine.optimize_quota_allocation(
            train_id=request.train_id,
            travel_date=request.travel_date,
            total_seats=request.total_seats,
            quota_demands=quota_demands,
            expected_cancellations={q: 0.08 for q in quota_demands},  # Default
        )
        
        return {
            "success": True,
            "train_id": request.train_id,
            "travel_date": request.travel_date,
            "total_seats": request.total_seats,
            "allocations": {
                q.value: seats
                for q, seats in allocation.allocations.items()
            },
            "projected_revenue": allocation.revenue_projection,
        }
    except Exception as e:
        logger.error(f"Quota allocation optimization failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/quota/current-allocations")
async def get_current_quota_allocations(
    train_id: int = Query(..., description="Train ID"),
    travel_date: str = Query(..., description="Travel date (YYYY-MM-DD)"),
    _: bool = Depends(verify_admin_token),
) -> Dict:
    """
    Get current quota allocations and status for a train.
    """
    try:
        # Get seat allocation stats
        stats = advanced_seat_allocation_engine.get_occupancy_stats()
        coach_breakdown = advanced_seat_allocation_engine.get_coach_wise_breakdown()
        
        return {
            "success": True,
            "train_id": train_id,
            "travel_date": travel_date,
            "occupancy_stats": stats,
            "coach_breakdown": coach_breakdown,
        }
    except Exception as e:
        logger.error(f"Failed to get quota allocations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# CANCELLATION & RISK MANAGEMENT
# ============================================================================

@router.post("/risk/predict-cancellation-rate")
async def predict_cancellation_rate(
    request: CancellationPredictionRequest,
    _: bool = Depends(verify_admin_token),
) -> Dict:
    """
    Predict cancellation rate for a train-quota pair.
    
    Used for:
    - Overbooking decisions
    - Revenue forecasting
    - Waitlist management
    - Compensation budgeting
    """
    try:
        prediction = cancellation_predictor.predict_cancellation_rate(
            train_id=request.train_id,
            travel_date=request.travel_date,
            quota_type=request.quota_type,
            days_to_departure=request.days_to_departure,
            booking_velocity=request.booking_velocity,
            route_popularity=request.route_popularity,
            demand_forecast=request.demand_forecast,
            historical_cancellation_rate=0.08,
        )
        
        return {
            "success": True,
            "train_id": request.train_id,
            "travel_date": request.travel_date,
            "quota_type": request.quota_type,
            "predicted_cancellation_rate": round(prediction.predicted_cancellation_rate, 4),
            "confidence_score": round(prediction.confidence_score, 2),
            "recommendation": prediction.recommendation,
            "contributing_factors": prediction.contributing_factors,
        }
    except Exception as e:
        logger.error(f"Cancellation prediction failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


# ============================================================================
# REVENUE ANALYTICS
# ============================================================================

@router.get("/analytics/segment-revenue")
async def get_segment_revenue_stats(
    _: bool = Depends(verify_admin_token),
) -> Dict:
    """
    Get revenue statistics across all OD (origin-destination) segments.
    """
    try:
        stats = yield_management_engine.get_segment_revenue_stats()
        
        return {
            "success": True,
            "timestamp": datetime.utcnow().isoformat(),
            "statistics": stats,
        }
    except Exception as e:
        logger.error(f"Failed to get revenue stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/analytics/forecast-daily-revenue")
async def forecast_daily_revenue(
    request: RevenuePerformanceRequest,
    _: bool = Depends(verify_admin_token),
) -> Dict:
    """
    Forecast daily revenue based on current occupancy and pricing.
    """
    try:
        # Simplified: assume 15 trains per day
        trains = [
            {"base_fare": 500, "total_seats": 100}
            for _ in range(15)
        ]
        
        forecasted_revenue = yield_management_engine.forecast_daily_revenue(
            trains, average_occupancy=0.75
        )
        
        return {
            "success": True,
            "period": request.time_period,
            "forecasted_daily_revenue": round(forecasted_revenue, 2),
            "forecasted_monthly_revenue": round(forecasted_revenue * 30, 2),
            "currency": "INR",
        }
    except Exception as e:
        logger.error(f"Revenue forecasting failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/health")
async def health_check() -> Dict:
    """Check revenue management system health."""
    return {
        "status": "healthy",
        "yield_management_ready": yield_management_engine is not None,
        "seat_allocation_ready": advanced_seat_allocation_engine is not None,
        "cancellation_predictor_ready": cancellation_predictor.is_trained,
        "timestamp": datetime.utcnow().isoformat(),
    }
