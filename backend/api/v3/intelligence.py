from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from database.session import get_db
from services.ml.reliability_engine import ReliabilityEngine
from services.intelligence.ghost_search import get_ghost_search_service

router = APIRouter(prefix="/intelligence", tags=["Intelligence"])

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
