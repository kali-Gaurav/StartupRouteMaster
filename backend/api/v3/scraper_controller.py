from fastapi import APIRouter, Depends, HTTPException, Query
from datetime import date, datetime
from typing import Optional, Dict, Any, List

from core.nexus.gatekeeper import nexus_gatekeeper
from services.scraper_sentinel import scraper_sentinel
from providers.clients.ntes_scraper import NtesScraperClient
from services.scraper.ntes_sync_service import ntes_sync_service
from providers.gateway import provider_gateway
from core.metrics import jit_metrics

router = APIRouter(prefix="/scraper", tags=["Nexus Scraper Control"], dependencies=[Depends(nexus_gatekeeper)])

@router.get("/health")
async def get_scraper_health():
    """Returns the current health and capacity of the Scraper Sentinel."""
    stats = await scraper_sentinel.get_stats()
    return {
        "status": "OPERATIONAL" if stats["available_contexts"] > 0 else "CONGESTED",
        "fiber_state": scraper_sentinel.state.value,
        "telemetry": stats,
        "timestamp": datetime.utcnow().isoformat()
    }

@router.post("/trigger/{train_no}")
async def trigger_manual_scrape(
    train_no: str, 
    journey_date: Optional[date] = None,
    bypass_cache: bool = Query(True, description="If true, ignore existing database and redis records.")
):
    """
    [Task 48.11] Manually forces an NTES scrape for a specific train.
    Useful for debugging or updating stale data.
    """
    if not journey_date:
        journey_date = date.today()
        
    logger_info = f"Manual trigger for {train_no} on {journey_date} (Bypass Cache: {bypass_cache})"
    
    if not bypass_cache:
        cached = await ntes_sync_service.get_cached_status(train_no, journey_date)
        if cached:
            return {"source": "cache", "data": cached}

    # Execute Scrape
    client = NtesScraperClient()
    raw_data = await client.get_live_status(train_no, journey_date=journey_date)
    
    if raw_data:
        # Sync to DB/Cache
        await ntes_sync_service.upsert_status(train_no, journey_date, raw_data)
        return {"source": "ntes_scraper", "data": raw_data}
    else:
        raise HTTPException(status_code=503, detail="NTES Scraper failed to retrieve data. System might be throttled.")

@router.get("/live-station/{station_code}")
async def get_live_station_status(station_code: str, hours: int = Query(2, ge=1, le=4)):
    """Fetch live station status (upcoming trains) directly via scraper."""
    data = await provider_gateway.get_live_station(station_code, within_hours=hours)
    if data:
        return data
    raise HTTPException(status_code=404, detail=f"No data available for station {station_code}")

@router.get("/stats")
async def get_scraper_stats():
    """Aggregated stats from the provider gateway and metrics engine."""
    # This assumes jit_metrics has scraper specific keys
    return {
        "ntes_calls": getattr(jit_metrics, "provider_calls", {}).get("ntes_scraper", 0),
        "ntes_success_rate": getattr(jit_metrics, "provider_success", {}).get("ntes_scraper", 1.0),
        "avg_latency": getattr(jit_metrics, "provider_latency", {}).get("ntes_scraper", 0)
    }
