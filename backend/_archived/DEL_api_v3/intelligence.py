from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from database.session import get_db
from database.models import User
from api.dependencies import get_current_user
from services.ml.reliability_engine import ReliabilityEngine
from services.intelligence.ghost_search import get_ghost_search_service
from services.sovereign.ledger import SovereignLedgerService
from core.sovereign.ab_engine import ab_engine
from pydantic import BaseModel

router = APIRouter(prefix="/intelligence", tags=["Intelligence"])

class IncentiveClaimRequest(BaseModel):
    amount: float
    nudge_id: str
    description: Optional[str] = None
    type: str = "redistribution"

@router.get("/reliability/heatmap")
async def get_reliability_heatmap(db: Session = Depends(get_db)):
    """
    [Phase C] Reliability Heatmap API.
    Returns statistical reliability scores for major station hubs.
    """
    # In a real scenario, this would aggregate data from the database.
    # For now, we return scores for major hubs.
    hubs = ["NDLS", "CSMT", "HWH", "MAS", "SBC", "PNBE", "ADI"]
    heatmap = {}
    engine = ReliabilityEngine()
    
    for hub in hubs:
        # Mocking categorical reliability for the hub
        heatmap[hub] = {
            "overall": 0.85 + (len(hub) % 10) / 100.0,
            "express": 0.78,
            "superfast": 0.92,
            "vibe_score": "HIGH" if len(hub) < 4 else "MEDIUM"
        }
    
    return {"status": "success", "data": heatmap}

@router.get("/ghost-search/status")
async def get_ghost_search_status(db: Session = Depends(get_db)):
    """
    Returns the current status of the Autonomous Re-accommodation monitor.
    """
    # This would typically query a shared state or the service instance
    return {
        "service": "ActiveJourneyMonitor",
        "status": "RUNNING",
        "active_monitors": 12, # Mocked count
        "reaccommodations_triggered_24h": 5
    }

@router.post("/ghost-search/simulate/{pnr}")
async def simulate_disruption(pnr: str, db: Session = Depends(get_db)):
    """
    Forces a Ghost Search simulation for a given PNR (for testing).
    """
    from database.models import Booking
    booking = db.query(Booking).filter(Booking.pnr_number == pnr).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
        
    ghost_svc = get_ghost_search_service(db)
    # Simulate a break at the first connection
    await ghost_svc._perform_ghost_search(booking, 0)
    
    
    return {"status": "success", "message": f"Ghost search triggered for {pnr}"}

# --- SOVEREIGN WALLET ENDPOINTS ---

@router.post("/sovereign/claim")
async def claim_sovereign_incentive(
    request: IncentiveClaimRequest,
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    [Phase 6] Claims a Sovereign Intelligence incentive.
    Updates the user's bonus credit balance and records the ledger entry.
    """
    try:
        result = SovereignLedgerService.claim_incentive(
            db=db,
            user_id=user.id,
            amount=request.amount,
            credit_type=request.type,
            description=request.description or "Sovereign Intelligence Redistribution Incentive",
            nudge_id=request.nudge_id
        )
        return result
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error while claiming incentive")

@router.get("/sovereign/wallet")
async def get_sovereign_wallet(
    user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    [Phase 6] Retrieves the user's Sovereign Wallet summary and active credits.
    """
    try:
        summary = SovereignLedgerService.get_wallet_summary(db, user.id)
        if "error" in summary:
            raise HTTPException(status_code=404, detail=summary["error"])
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal server error while fetching wallet")

@router.post("/ab/convert")
async def record_ab_conversion(
    payload: Dict[str, Any],
    user: User = Depends(get_current_user)
):
    """
    [SOVEREIGN] Record A/B Testing Conversion.
    """
    experiment_id = payload.get("experiment_id", "nudge_tone_optimization")
    variant = payload.get("variant")
    goal = payload.get("goal", "conversion")
    
    if not variant:
        raise HTTPException(status_code=400, detail="Variant is required")
        
    await ab_engine.record_conversion(user.id, experiment_id, variant, goal)
    return {"status": "recorded"}
