from fastapi import APIRouter, Depends, HTTPException, WebSocket, WebSocketDisconnect
from typing import Dict, List, Any
from services.multi_layer_cache import multi_layer_cache
from dependencies import get_route_engine, get_db
from datetime import datetime
from sqlalchemy.orm import Session
import time
import asyncio
import json
import logging

logger = logging.getLogger(__name__)
start_time = time.time()

router = APIRouter(prefix="/admin", tags=["System Administration"])

@router.post("/cache/clear")
async def clear_cache():
    """Clear all Redis cache layers."""
    await multi_layer_cache.initialize()
    if not multi_layer_cache.redis:
        raise HTTPException(status_code=500, detail="Redis not connected")
    
    await multi_layer_cache.redis.flushall()
    return {"message": "Redis cache cleared successfully"}

@router.post("/graph/rebuild")
async def rebuild_graph(engine=Depends(get_route_engine)):
    """Force a fresh build of the memory-resident graph snapshot."""
    await engine.rebuild_snapshot(datetime.now())
    return {"message": "Graph rebuild triggered", "timestamp": datetime.now()}

@router.get("/system/health")
async def get_system_health():
    """Aggregate CPU, RAM, and DB disk usage (TODO #12)."""
    import psutil
    import os
    
    def get_dir_size(path):
        total = 0
        try:
            if not os.path.exists(path): return 0
            for entry in os.scandir(path):
                if entry.is_file(): total += entry.stat().size
                elif entry.is_dir(): total += get_dir_size(entry.path)
        except: pass
        return total

    return {
        "cpu_usage_percent": psutil.cpu_percent(),
        "memory_info": psutil.virtual_memory()._asdict(),
        "db_storage_bytes": get_dir_size("backend/database"),
        "uptime_seconds": time.time() - start_time
    }

@router.get("/cache/stats")
async def get_cache_stats():
    """Visualize Redis hit/miss ratios (TODO #13)."""
    await multi_layer_cache.initialize()
    # Simple aggregation from metrics
    return {
        "infrastructure": multi_layer_cache.metrics['infrastructure_cache'].__dict__,
        "query": multi_layer_cache.metrics['query_cache'].__dict__,
        "availability": multi_layer_cache.metrics['availability_cache'].__dict__
    }

@router.get("/vpa/stats")
async def get_vpa_stats():
    """Task 1.7: Real-time VPA utilization dashboard."""
    from services.merchant_vpa_service import merchant_vpa_service
    # Note: Need to implement get_dashboard_stats in MerchantVPAService first if not there
    # It was in the old version but I refactored it. I'll re-add a database version.
    db = SessionLocal()
    try:
        from database.models import MerchantVPA
        vpas = db.query(MerchantVPA).all()
        stats = []
        for v in vpas:
            stats.append({
                "vpa": v.vpa,
                "name": v.name,
                "utilization_pct": min(100.0, (v.current_daily_volume / v.daily_limit) * 100),
                "volume": v.current_daily_volume,
                "limit": v.daily_limit,
                "is_active": v.is_active
            })
        return stats
    finally:
        db.close()

from database.models import ETLMetadata, Booking, EscrowStatus, User
from services.ws_manager import ws_manager
from pydantic import BaseModel

class BookingCompleteRequest(BaseModel):
    pnr_number: str
    message: str = "Booking confirmed and ticket sent!"

class BookingFailRequest(BaseModel):
    reason: str

@router.get("/bookings/pending")
async def get_pending_bookings(db: Session = Depends(get_db)):
    """List all AGENT_BOOKING requests that are VERIFIED and awaiting Admin action."""
    bookings = db.query(Booking).filter(
        Booking.escrow_status == EscrowStatus.VERIFIED,
        Booking.service_type == "AGENT_BOOKING"
    ).all()
    return bookings

@router.post("/reconcile")
async def force_reconcile():
    """Manual trigger for Task 7: Reconciliation Service."""
    from services.reconciliation_service import reconciliation_service
    result = await reconciliation_service.reconcile_all_pending()
    return result

@router.post("/bookings/{booking_id}/complete")
async def complete_booking(
    booking_id: str,
    payload: BookingCompleteRequest,
    db: Session = Depends(get_db)
):
    """Mark a booking as COMPLETED and notify the user via WebSocket."""
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    booking.escrow_status = EscrowStatus.COMPLETED
    booking.pnr_number = payload.pnr_number
    booking.escrow_message = payload.message
    booking.booking_status = "confirmed"
    booking.is_unlocked = True
    db.commit()
    
    await ws_manager.broadcast_log(booking_id, f"🎉 Ticket Confirmed by Admin! PNR: {payload.pnr_number}", "COMPLETED")
    return {"message": "Booking completed successfully"}

@router.post("/bookings/{booking_id}/fail")
async def fail_booking(
    booking_id: str,
    payload: BookingFailRequest,
    db: Session = Depends(get_db)
):
    """Mark a booking as FAILED and notify the user."""
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    booking.escrow_status = EscrowStatus.FAILED
    booking.escrow_message = payload.reason
    db.commit()
    
    await ws_manager.broadcast_log(booking_id, f"❌ Booking Failed: {payload.reason}", "FAILED")
    return {"message": "Booking marked as failed"}

@router.get("/bookings/{booking_id}/details")
async def get_booking_details(
    booking_id: str,
    db: Session = Depends(get_db)
):
    """
    Fetch comprehensive details for IRCTC booking manual processing.
    Includes passenger list and train details.
    """
    booking = db.query(Booking).filter(Booking.id == booking_id).first()
    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")
    
    # Task 6.4: Credential Retrieval (Mocked for now or using vault service)
    irctc_creds = None
    if booking.user.opt_in_persistent_creds:
        from services.credential_vault import credential_vault
        # This would require user decryption key in a real flow
        irctc_creds = {"username": "user_irctc_id", "status": "encrypted"}

    return {
        "id": booking.id,
        "train_number": booking.train_number,
        "travel_date": booking.travel_date.isoformat(),
        "passengers": [
            {"name": p.full_name, "age": p.age, "gender": p.gender}
            for p in booking.passenger_details
        ],
        "berth_preference": booking.berth_preference,
        "service_type": booking.service_type,
        "amount_paid": booking.amount_paid,
        "irctc_creds": irctc_creds
    }

@router.get("/etl/status")
async def get_etl_status(db: Session = Depends(get_db)):
    """Show the latest ETLMetadata runs and sync progress (TODO #16)."""
    from database.models import ETLMetadata
    runs = db.query(ETLMetadata).order_by(ETLMetadata.updated_at.desc()).limit(10).all()
    return runs

@router.websocket("/ws/metrics")
async def websocket_metrics(websocket: WebSocket):
    """
    Push real-time system metrics to dashboard via WebSocket (Suggestion #1).
    """
    await websocket.accept()
    import psutil
    try:
        while True:
            cpu = psutil.cpu_percent()
            mem = psutil.virtual_memory().percent
            
            p50, p99 = 0, 0
            try:
                await multi_layer_cache.initialize()
                if multi_layer_cache.redis:
                    curr_min = int(time.time() // 60)
                    # Fetch last 2 minutes of latencies
                    keys = [f"metrics:latency:{m}" for m in range(curr_min-1, curr_min+1)]
                    all_latencies = []
                    for k in keys:
                        vals = await multi_layer_cache.redis.zrange(k, 0, -1, withscores=True)
                        all_latencies.extend([float(s) for _, s in vals])
                    
                    if all_latencies:
                        all_latencies.sort()
                        p50 = all_latencies[len(all_latencies)//2]
                        p99 = all_latencies[int(len(all_latencies)*0.99)]
            except Exception as e:
                logger.error(f"WS Metric Error: {e}")

            await websocket.send_json({
                "cpu": cpu,
                "mem": mem,
                "p50": round(p50, 2),
                "p99": round(p99, 2),
                "timestamp": datetime.utcnow().isoformat()
            })
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        logger.info("Metrics WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
