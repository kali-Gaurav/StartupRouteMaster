from fastapi import APIRouter, Depends, HTTPException
from typing import Optional
from services.rapidapi_provider import rapidapi_provider, RapidApiProvider
from schemas.rapidapi_models import LiveStatus, PNRStatus
from utils.responses import success_response
import logging

logger = logging.getLogger("api.external")
router = APIRouter(prefix="/external", tags=["External Providers"])

@router.get("/live-status/{train_no}")
async def get_live_status(train_no: str, provider: RapidApiProvider = Depends(lambda: rapidapi_provider)):
    """Get the live status of a train from the external RapidAPI provider."""
    if not provider.is_healthy:
        logger.error(f"EXTERNAL_API_UNHEALTHY | LiveStatus | {train_no}")
        raise HTTPException(status_code=503, detail="External API provider is not available.")
    
    live_status = await provider.get_live_train_status(train_no)
    if not live_status:
        raise HTTPException(status_code=404, detail="Train not found or error fetching live status.")
        
    logger.info(f"EXTERNAL_API_SUCCESS | LiveStatus | {train_no}")
    return success_response(data=live_status)

@router.get("/pnr-status/{pnr_no}")
async def get_pnr_status(pnr_no: str, provider: RapidApiProvider = Depends(lambda: rapidapi_provider)):
    """Get the PNR status from the external RapidAPI provider."""
    if not provider.is_healthy:
        logger.error(f"EXTERNAL_API_UNHEALTHY | PNRStatus | {pnr_no}")
        raise HTTPException(status_code=503, detail="External API provider is not available.")
        
    pnr_status = await provider.get_pnr_status(pnr_no)
    if not pnr_status:
        raise HTTPException(status_code=404, detail="PNR not found or error fetching status.")
        
    logger.info(f"EXTERNAL_API_SUCCESS | PNRStatus | {pnr_no}")
    return success_response(data=pnr_status)
