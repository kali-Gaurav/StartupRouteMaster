import logging
import asyncio
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database.session import SessionUser, init_db
from database.models import Booking, BookingStatus, AuditLog
from services.booking_verification_service import booking_verification_service

logger = logging.getLogger("pnr-monitor")

class PNRMonitorService:
    """
    [Task 4.3] Long-polling PNR Monitor.
    Periodically checks the live status of all PNRs in the system.
    """
    
    def __init__(self):
        self._is_running = False

    async def poll_active_pnrs(self):
        """
        Background task to refresh PNR statuses.
        """
        if self._is_running: return
        self._is_running = True
        
        try:
            logger.info("📡 Starting PNR Monitoring Cycle...")
            # Use SessionUser (Sync for simplicity in background tasks if not async)
            with SessionUser() as db:
                # Find bookings that are active and not travelled yet
                # Filter for bookings where travel_date is today or in future
                active_bookings = db.query(Booking).filter(
                    Booking.booking_status.in_(["confirmed", "pending", "waitlist"]),
                    Booking.pnr_number != None
                ).all()
                
                logger.info(f"Found {len(active_bookings)} PNRs to monitor.")
                
                for b in active_bookings:
                    try:
                        # 1. Fetch Live Verification
                        res = await booking_verification_service.verify_booking_details(
                            pnr_number=b.pnr_number,
                            train_number=b.train_number,
                            travel_date=b.travel_date.strftime("%Y-%m-%d") if b.travel_date else None
                        )
                        
                        # 2. Status Update Logic
                        pnr_status = res.get("pnr_status")
                        if pnr_status and pnr_status.get("status"):
                            new_status = pnr_status["status"].lower()
                            
                            if new_status != b.booking_status:
                                logger.info(f"PNR Status Change detected for {b.pnr_number}: {b.booking_status} -> {new_status}")
                                
                                # Log the change
                                audit = AuditLog(
                                    entity_type="Booking",
                                    entity_id=b.id,
                                    action="PNR_MONITOR_UPDATE",
                                    old_value=b.booking_status,
                                    new_value=new_status,
                                    reason=f"Status updated via auto-polling."
                                )
                                db.add(audit)
                                b.booking_status = new_status
                                
                        # 3. Handle Issues (Cancellations)
                        if "Train is cancelled" in str(res.get("issues", [])):
                             # Handle high priority cancellation alert
                             pass
                                
                        db.commit()
                        
                        # Throttle to avoid rate limiting
                        await asyncio.sleep(2)
                        
                    except Exception as e:
                        logger.error(f"Failed to poll PNR {b.pnr_number}: {e}")
                        
            logger.info("✅ PNR Monitoring Cycle Complete.")
        except Exception as e:
            logger.error(f"❌ PNR Monitor Fail: {e}")
        finally:
            self._is_running = False

pnr_monitor_service = PNRMonitorService()
