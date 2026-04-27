"""
Redistribution Execution API Endpoints

Provides REST API for:
- Executing redistribution offers
- Tracking redistribution status
- Managing incentive credits
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, status
from typing import Dict, Any, List, Optional
from datetime import datetime
from pydantic import BaseModel

from database.session import get_db
from services.redistribution_booking_integrator import get_redistribution_integrator, RedistributionResult

logger = logging.getLogger("api.redistribution_execution")

router = APIRouter(prefix="/api/redistribution", tags=["Redistribution"])


class RedistributionExecuteRequest(BaseModel):
    """Request to execute redistribution"""
    offer_id: str
    passenger_id: str
    accepted: bool = True


class RedistributionStatusRequest(BaseModel):
    """Request for redistribution status"""
    booking_id: str


class RedistributionResponse(BaseModel):
    """Redistribution execution response"""
    success: bool
    original_booking_id: Optional[str] = None
    new_booking_id: Optional[str] = None
    new_pnr: Optional[str] = None
    incentive_amount: float = 0.0
    message: str = ""
    error: Optional[str] = None


class RedistributionStatusResponse(BaseModel):
    """Redistribution status response"""
    status: str  # not_offered, pending, accepted, rejected
    offer_id: Optional[str] = None
    alternative_route: Optional[str] = None
    incentive_amount: float = 0.0
    created_at: Optional[str] = None
    expires_at: Optional[str] = None


@router.post("/execute", response_model=RedistributionResponse)
async def execute_redistribution(
    request: RedistributionExecuteRequest,
    db=Depends(get_db)
):
    """
    Execute a redistribution offer.
    
    When a passenger accepts an offer:
    1. Original booking is cancelled
    2. New booking is created on alternative route
    3. Incentive credit is applied
    
    When a passenger rejects:
    1. Offer is marked as rejected
    2. Metrics are updated
    """
    try:
        integrator = get_redistribution_integrator(db)
        result = await integrator.execute_redistribution(
            offer_id=request.offer_id,
            passenger_id=request.passenger_id,
            accepted=request.accepted
        )
        
        return RedistributionResponse(
            success=result.success,
            original_booking_id=result.original_booking_id,
            new_booking_id=result.new_booking_id,
            new_pnr=result.new_pnr,
            incentive_amount=result.incentive_amount,
            message=result.message,
            error=result.error
        )
        
    except Exception as e:
        logger.error(f"Redistribution execution error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/status/{booking_id}", response_model=RedistributionStatusResponse)
async def get_redistribution_status(
    booking_id: str,
    db=Depends(get_db)
):
    """
    Get redistribution status for a booking.
    
    Returns:
    - not_offered: No redistribution offer made
    - pending: Offer made but not responded
    - accepted: Offer accepted, redistribution complete
    - rejected: Offer rejected
    """
    try:
        integrator = get_redistribution_integrator(db)
        redistribution_status = integrator.get_redistribution_status(booking_id)
        
        return RedistributionStatusResponse(
            status=redistribution_status.get("status", "unknown"),
            offer_id=redistribution_status.get("offer_id"),
            alternative_route=redistribution_status.get("alternative_route"),
            incentive_amount=redistribution_status.get("incentive_amount", 0.0),
            created_at=redistribution_status.get("created_at"),
            expires_at=redistribution_status.get("expires_at")
        )
        
    except Exception as e:
        logger.error(f"Status check error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/history/{user_id}")
async def get_user_redistribution_history(
    user_id: str,
    limit: int = 10,
    db=Depends(get_db)
):
    """
    Get redistribution history for a user.
    
    Returns list of past redistributions with details.
    """
    try:
        from database.models_redistribution import RedistributionOffer
        
        offers = db.query(RedistributionOffer).filter(
            RedistributionOffer.passenger_id == user_id
        ).order_by(
            RedistributionOffer.offered_at.desc()
        ).limit(limit).all()
        
        return {
            "user_id": user_id,
            "total_offers": len(offers),
            "accepted": sum(1 for o in offers if o.status == "accepted"),
            "rejected": sum(1 for o in offers if o.status == "rejected"),
            "history": [
                {
                    "offer_id": o.offer_id,
                    "original_route": f"{o.original_source}->{o.original_destination}",
                    "alternative_route": f"{o.alternative_source}->{o.alternative_destination}",
                    "incentive": o.incentive_amount,
                    "status": o.status,
                    "offered_at": o.offered_at.isoformat() if o.offered_at else None
                }
                for o in offers
            ]
        }
        
    except Exception as e:
        logger.error(f"History fetch error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/incentives/{user_id}")
async def get_user_incentives(
    user_id: str,
    db=Depends(get_db)
):
    """
    Get incentive credits for a user.
    
    Returns available credits and usage history.
    """
    try:
        from database.models_redistribution import IncentiveCredit
        
        credits = db.query(IncentiveCredit).filter(
            IncentiveCredit.user_id == user_id,
            IncentiveCredit.status == "active"
        ).all()
        
        total_available = sum(c.amount - c.used_amount for c in credits)
        
        return {
            "user_id": user_id,
            "total_available": total_available,
            "credits": [
                {
                    "credit_id": c.credit_id,
                    "amount": c.amount,
                    "used_amount": c.used_amount,
                    "remaining": c.amount - c.used_amount,
                    "credit_type": c.credit_type,
                    "expires_at": c.expires_at.isoformat() if c.expires_at else None,
                    "status": c.status
                }
                for c in credits
            ]
        }
        
    except Exception as e:
        logger.error(f"Incentive fetch error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


# Import logger at module level
import logging
logger = logging.getLogger(__name__)