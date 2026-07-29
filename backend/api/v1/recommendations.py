"""
RouteMaster v1 Recommendations API
=================================
GET /api/v1/recommendations?source=NDLS&destination=BCT&date=2026-06-10
Returns personalized route recommendations based on user history and preferences.
"""
from __future__ import annotations

import logging
import time
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query, Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from database.session import get_db
from core.data_utils.structures import Persona
from services.recommendation_service import get_recommendation_engine

logger = logging.getLogger("routemaster.v1.recommendations")
router = APIRouter(prefix="/recommendations", tags=["recommendations-v1"])


# ── Response Models ──────────────────────────────────────────────────────────

class RouteRecommendation(BaseModel):
    """Single route recommendation."""
    journey_id: str
    departure_time: str
    arrival_time: str
    total_duration: int  # minutes
    total_cost: float  # rupees
    num_transfers: int
    availability_status: str
    confidence_score: float  # 0-1
    reason: str  # Why this was recommended
    metadata: Dict[str, Any] = {}


class RecommendationsResponse(BaseModel):
    """Recommendations API response."""
    status: str = "success"
    source: str
    destination: str
    travel_date: str
    recommendations: List[Dict[str, Any]]
    reasons: List[str]
    metadata: Dict[str, Any] = {}


# ── Helpers ──────────────────────────────────────────────────────────────────

def _time_str(t: str) -> str:
    """Normalise 'HH:MM:SS' → 'HH:MM'."""
    if not t:
        return "--:--"
    parts = str(t).split(":")
    if len(parts) >= 2:
        return f"{parts[0].zfill(2)}:{parts[1].zfill(2)}"
    return t


def _format_recommendation(route_dict: Dict[str, Any], reason: str, confidence: float) -> Dict[str, Any]:
    """Format a single recommendation for the response."""
    # Extract basic info from route dict
    legs = route_dict.get("legs", [])
    first_leg = legs[0] if legs else {}
    last_leg = legs[-1] if legs else {}

    return {
        "journey_id": route_dict.get("journey_id", ""),
        "departure_time": first_leg.get("departure_time", "--:--"),
        "arrival_time": last_leg.get("arrival_time", "--:--"),
        "total_duration": route_dict.get("total_duration", 0),
        "total_cost": route_dict.get("total_cost", 0),
        "num_transfers": route_dict.get("num_transfers", 0),
        "availability_status": route_dict.get("availability_status", "UNKNOWN"),
        "confidence_score": confidence,
        "reason": reason,
        "legs": legs,
        "metadata": route_dict.get("metadata", {})
    }


async def get_user_id_from_request(request: Request) -> str:
    """Extract user ID from request context or headers."""
    # Check request state
    if hasattr(request, "state") and hasattr(request.state, "user_id"):
        return request.state.user_id

    # Check headers
    auth_header = request.headers.get("X-User-ID")
    if auth_header:
        return auth_header

    return "anonymous"


# ── Endpoints ────────────────────────────────────────────────────────────────

@router.get("/", response_model=RecommendationsResponse)
async def get_recommendations(
    request: Request,
    source: str = Query(..., min_length=2, max_length=10, description="Origin station code e.g. NDLS"),
    destination: str = Query(..., min_length=2, max_length=10, description="Destination station code e.g. BCT"),
    date: Optional[str] = Query(None, description="Travel date YYYY-MM-DD, default today"),
    persona: str = Query("COMFORT", description="Persona: COMFORT, ECONOMY, PREMIUM, FAMILY, SPECIAL"),
    limit: int = Query(10, ge=1, le=30),
    db: Session = Depends(get_db)
):
    """
    Get personalized route recommendations.

    Returns top-N routes based on:
    - User's search and booking history
    - Travel preferences
    - Route popularity and demand
    - Seat availability
    - Pricing alignment with persona

    Query Parameters:
    - source: Origin station code (required)
    - destination: Destination station code (required)
    - date: Travel date in YYYY-MM-DD format (optional, defaults to today)
    - persona: User persona for ranking (optional, defaults to COMFORT)
      Values: COMFORT, ECONOMY, PREMIUM, FAMILY, SPECIAL
    - limit: Number of recommendations to return (1-30, default 10)

    Returns:
    - recommendations: List of recommended routes
    - reasons: Human-readable reasons for recommendations
    - metadata: Algorithm info, generated timestamp, confidence scores
    """
    start_time = time.perf_counter()

    try:
        # Normalize inputs
        src = source.upper().strip()
        dst = destination.upper().strip()

        if src == dst:
            raise HTTPException(
                status_code=400,
                detail="Source and destination cannot be the same."
            )

        # Parse travel date
        try:
            travel_date = datetime.strptime(date, "%Y-%m-%d").date() if date else datetime.now().date()
            date_str = travel_date.isoformat()
        except ValueError:
            travel_date = datetime.now().date()
            date_str = travel_date.isoformat()

        # Validate persona
        try:
            persona_obj = Persona(persona.upper())
        except ValueError:
            logger.warning(f"Invalid persona '{persona}'. Defaulting to COMFORT.")
            persona_obj = Persona.COMFORT

        # Get user ID
        user_id = await get_user_id_from_request(request)

        # Get recommendation engine
        engine = get_recommendation_engine(db)

        # Generate recommendations
        result = await engine.get_recommendations(
            user_id=user_id,
            source=src,
            destination=dst,
            travel_date=date_str,
            persona=persona_obj,
            limit=limit
        )

        # Format response
        formatted_recommendations = []
        reasons = result.get("reasons", [])
        confidence_scores = result.get("metadata", {}).get("confidence_scores", [])

        for i, rec in enumerate(result.get("recommendations", [])):
            confidence = confidence_scores[i] if i < len(confidence_scores) else 0.8
            reason = reasons[i] if i < len(reasons) else "Based on your preferences"
            formatted_rec = _format_recommendation(rec, reason, confidence)
            formatted_recommendations.append(formatted_rec)

        latency_ms = round((time.perf_counter() - start_time) * 1000)

        return {
            "status": "success",
            "source": src,
            "destination": dst,
            "travel_date": date_str,
            "recommendations": formatted_recommendations,
            "reasons": reasons,
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "algorithm_version": "1.0",
                "persona": persona_obj.value,
                "user_id": user_id if user_id != "anonymous" else None,
                "confidence_scores": confidence_scores,
                "latency_ms": latency_ms,
                "total_recommendations": len(formatted_recommendations)
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Recommendation generation failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to generate recommendations. Please try again later."
        )


@router.get("/trending", response_model=RecommendationsResponse)
async def get_trending_routes(
    request: Request,
    source: Optional[str] = Query(None, description="Filter by origin (optional)"),
    destination: Optional[str] = Query(None, description="Filter by destination (optional)"),
    date: Optional[str] = Query(None, description="Travel date YYYY-MM-DD"),
    limit: int = Query(10, ge=1, le=30),
    db: Session = Depends(get_db)
):
    """
    Get trending routes based on recent search activity and demand.

    Returns routes that are:
    - High search volume
    - High demand
    - Available seats
    - Good availability probability

    Query Parameters:
    - source: Filter by origin (optional)
    - destination: Filter by destination (optional)
    - date: Travel date (optional, defaults to today)
    - limit: Number of recommendations (1-30, default 10)

    Returns:
    - recommendations: List of trending routes
    - metadata: Generation timestamp, confidence scores
    """
    start_time = time.perf_counter()

    try:
        # Parse travel date
        try:
            travel_date = datetime.strptime(date, "%Y-%m-%d").date() if date else datetime.now().date()
            date_str = travel_date.isoformat()
        except ValueError:
            travel_date = datetime.now().date()
            date_str = travel_date.isoformat()

        engine = get_recommendation_engine(db)

        # If source and destination provided, get trending for that route
        if source and destination:
            src = source.upper().strip()
            dst = destination.upper().strip()

            if src == dst:
                raise HTTPException(
                    status_code=400,
                    detail="Source and destination cannot be the same."
                )

            result = await engine.get_recommendations(
                user_id="trending_query",
                source=src,
                destination=dst,
                travel_date=date_str,
                persona=Persona.COMFORT,
                limit=limit
            )

            formatted_recommendations = []
            reasons = result.get("reasons", [])
            confidence_scores = result.get("metadata", {}).get("confidence_scores", [])

            for i, rec in enumerate(result.get("recommendations", [])):
                confidence = confidence_scores[i] if i < len(confidence_scores) else 0.8
                reason = "🔥 " + (reasons[i] if i < len(reasons) else "Trending route")
                formatted_rec = _format_recommendation(rec, reason, confidence)
                formatted_recommendations.append(formatted_rec)

            latency_ms = round((time.perf_counter() - start_time) * 1000)

            return {
                "status": "success",
                "source": src,
                "destination": dst,
                "travel_date": date_str,
                "recommendations": formatted_recommendations,
                "reasons": [f"🔥 {r}" for r in reasons],
                "metadata": {
                    "generated_at": datetime.now().isoformat(),
                    "category": "trending",
                    "latency_ms": latency_ms,
                    "total_recommendations": len(formatted_recommendations)
                }
            }
        else:
            # Return empty result if filters not specified
            return {
                "status": "success",
                "source": source or "any",
                "destination": destination or "any",
                "travel_date": date_str,
                "recommendations": [],
                "reasons": ["Specify source and destination for trending routes"],
                "metadata": {
                    "generated_at": datetime.now().isoformat(),
                    "category": "trending",
                    "latency_ms": 0,
                    "total_recommendations": 0
                }
            }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Trending routes retrieval failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to retrieve trending routes. Please try again later."
        )


@router.get("/personalized", response_model=RecommendationsResponse)
async def get_personalized_recommendations(
    request: Request,
    source: str = Query(..., min_length=2, max_length=10, description="Origin station code"),
    destination: str = Query(..., min_length=2, max_length=10, description="Destination station code"),
    date: Optional[str] = Query(None, description="Travel date YYYY-MM-DD"),
    limit: int = Query(10, ge=1, le=30),
    db: Session = Depends(get_db)
):
    """
    Get personalized recommendations based on user history.

    This endpoint requires authentication and uses:
    - User's previous searches and bookings
    - User's travel preferences (time, class, price sensitivity)
    - User's booking patterns

    Returns recommendations tailored to individual user behavior.

    Query Parameters:
    - source: Origin station code (required)
    - destination: Destination station code (required)
    - date: Travel date (optional)
    - limit: Number of recommendations (1-30, default 10)

    Authentication:
    - Requires valid user session via X-User-ID header or request context
    """
    start_time = time.perf_counter()

    try:
        # Normalize inputs
        src = source.upper().strip()
        dst = destination.upper().strip()

        if src == dst:
            raise HTTPException(
                status_code=400,
                detail="Source and destination cannot be the same."
            )

        # Parse travel date
        try:
            travel_date = datetime.strptime(date, "%Y-%m-%d").date() if date else datetime.now().date()
            date_str = travel_date.isoformat()
        except ValueError:
            travel_date = datetime.now().date()
            date_str = travel_date.isoformat()

        # Get authenticated user
        user_id = await get_user_id_from_request(request)
        if user_id == "anonymous":
            raise HTTPException(
                status_code=401,
                detail="Authentication required for personalized recommendations"
            )

        # Get recommendation engine
        engine = get_recommendation_engine(db)

        # Detect user's preferred persona from history
        # For now, default to COMFORT
        user_persona = Persona.COMFORT

        # Generate recommendations
        result = await engine.get_recommendations(
            user_id=user_id,
            source=src,
            destination=dst,
            travel_date=date_str,
            persona=user_persona,
            limit=limit
        )

        # Format response
        formatted_recommendations = []
        reasons = result.get("reasons", [])
        confidence_scores = result.get("metadata", {}).get("confidence_scores", [])

        for i, rec in enumerate(result.get("recommendations", [])):
            confidence = confidence_scores[i] if i < len(confidence_scores) else 0.8
            reason = reasons[i] if i < len(reasons) else "Based on your profile"
            formatted_rec = _format_recommendation(rec, reason, confidence)
            formatted_recommendations.append(formatted_rec)

        latency_ms = round((time.perf_counter() - start_time) * 1000)

        return {
            "status": "success",
            "source": src,
            "destination": dst,
            "travel_date": date_str,
            "recommendations": formatted_recommendations,
            "reasons": reasons,
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "algorithm_version": "1.0",
                "category": "personalized",
                "user_id": user_id,
                "confidence_scores": confidence_scores,
                "latency_ms": latency_ms,
                "total_recommendations": len(formatted_recommendations)
            }
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Personalized recommendations failed: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail="Failed to generate personalized recommendations. Please try again later."
        )
