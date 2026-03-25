from fastapi import APIRouter, Depends, HTTPException
from typing import Optional

from services.rapidapi_provider import rapidapi_provider, RapidApiProvider
from schemas.rapidapi_models import LiveStatus, PNRStatus

router = APIRouter()

@router.get("/external/live-status/{train_no}", response_model=Optional[LiveStatus])
async def get_live_status(train_no: str, provider: RapidApiProvider = Depends(lambda: rapidapi_provider)):
    """
    Get the live status of a train from the external RapidAPI provider.
    """
    if not provider.is_healthy:
        raise HTTPException(status_code=503, detail="External API provider is not available.")
    
    live_status = await provider.get_train_live_status(train_no)
    
    if not live_status:
        raise HTTPException(status_code=404, detail="Train not found or error fetching live status.")
        
    return live_status

@router.get("/external/pnr-status/{pnr_no}", response_model=Optional[PNRStatus])
async def get_pnr_status(pnr_no: str, provider: RapidApiProvider = Depends(lambda: rapidapi_provider)):
    """
    Get the PNR status from the external RapidAPI provider.
    """
    if not provider.is_healthy:
        raise HTTPException(status_code=503, detail="External API provider is not available.")
        
    pnr_status = await provider.get_pnr_status(pnr_no)
    
    if not pnr_status:
        raise HTTPException(status_code=404, detail="PNR not found or error fetching status.")
        
    return pnr_status
