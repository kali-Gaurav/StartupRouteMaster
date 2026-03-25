import asyncio
import logging
import json
from datetime import datetime, timedelta, date
from typing import List, Optional, Dict, Any
from sqlalchemy import select, update, or_, and_
from sqlalchemy.ext.asyncio import AsyncSession

# Import models using relative paths or absolute depending on project structure
# In this project, it seems we use direct absolute imports from 'database' and 'backend'
# but 'backend' itself is often part of the root.
# Let's check imports in other files.
from database.models import BookingMonitor
from providers.gateway import provider_gateway
from providers.models import AlertMessage, UnifiedLiveStatus
from core.redis import async_redis_client
from database.session import AsyncSessionUser

logger = logging.getLogger("routemaster.monitoring")

class AlertQueueService:
    """
    Service for reliably queuing alerts into Redis for consumption by 
    notification workers (Telegram, Push, SMS).
    """
    def __init__(self, redis_client=async_redis_client):
        self.redis = redis_client
        self.queue_name = "booking_alerts_queue"

    async def queue_alert(self, alert_data: Dict[str, Any]):
        """
        Submits a validated alert to the Redis queue.
        """
        try:
            # Validate with Pydantic model
            alert = AlertMessage(**alert_data)
            payload = alert.model_dump_json() if hasattr(alert, 'model_dump_json') else alert.json()
            await self.redis.rpush(self.queue_name, payload)
            logger.info(f"🔔 Alert queued for booking {alert.booking_id} (Type: {alert.alert_type})")
        except Exception as e:
            logger.error(f"❌ Failed to queue alert: {e}", exc_info=True)

class BookingMonitorService:
    """
    Task 15: Background Monitoring Scheduler.
    Identifies bookings needing status updates, fetches fresh data from Provider Gateway,
    detects changes in status (delays, cancellations, PNR updates), and triggers alerts.
    """
    def __init__(self, alert_queue: AlertQueueService):
        self.alert_queue = alert_queue
        # Frequencies based on proximity to travel
        self.active_check_interval = timedelta(minutes=15)
        self.upcoming_check_interval = timedelta(hours=1)
        self.monitoring_window_hours = 48
        self._is_running = False

    async def get_bookings_for_monitoring(self, session: AsyncSession) -> List[BookingMonitor]:
        """
        Queries the database for bookings requiring a fresh check.
        Criteria:
        - Monitoring is active
        - Within travel date window (Yesterday to +2 days)
        - Last check time is older than the required interval
        """
        now = datetime.utcnow()
        today = now.date()
        
        active_cutoff = now - self.active_check_interval
        upcoming_cutoff = now - self.upcoming_check_interval
        window_start = today - timedelta(days=1)
        window_end = today + timedelta(days=2)

        # Build dynamic query
        query = select(BookingMonitor).where(
            and_(
                BookingMonitor.is_monitoring_active == True,
                BookingMonitor.travel_date.between(window_start, window_end),
                or_(
                    BookingMonitor.last_check_timestamp == None, # Never checked
                    and_(
                        BookingMonitor.travel_date == today,
                        BookingMonitor.last_check_timestamp < active_cutoff
                    ),
                    and_(
                        BookingMonitor.travel_date > today,
                        BookingMonitor.last_check_timestamp < upcoming_cutoff
                    )
                )
            )
        ).limit(100) # Process in batches

        result = await session.execute(query)
        return list(result.scalars().all())

    async def detect_changes(self, booking: BookingMonitor, 
                             latest_live: Optional[UnifiedLiveStatus], 
                             latest_pnr: Optional[Dict[str, Any]]):
        """
        Compares latest data fetch against stored snapshots in the database.
        Triggers an alert if significant deviations are found.
        """
        alert_triggered = False
        alert_details = []
        alert_type = "booking_update"

        # 1. LIVE STATUS CHANGE DETECTION
        if latest_live:
            last_live = booking.last_known_live_status or {}
            
            # Detect Running Status Changes (e.g., On Time -> Delayed)
            if latest_live.running_status != last_live.get("running_status"):
                alert_details.append(f"Train status update: {latest_live.running_status}")
                alert_triggered = True
                if latest_live.running_status == "Cancelled":
                    alert_type = "cancellation"

            # Detect Delay Escalation
            delay_threshold = booking.alert_preferences.get("notify_on_delay_minutes", 60)
            if latest_live.delay_minutes > delay_threshold and last_live.get("delay_minutes", 0) <= delay_threshold:
                alert_details.append(f"Delay crossed threshold ({delay_threshold}m): Currently {latest_live.delay_minutes}m late.")
                alert_triggered = True
                alert_type = "delay_warning"

            # Snapshot current status for next check
            booking.last_known_live_status = latest_live.model_dump()

        # 2. PNR STATUS CHANGE DETECTION
        if latest_pnr:
            last_pnr = booking.last_known_pnr_status or {}
            
            # Detect Booking Status confirmation (e.g., WL -> CNF)
            current_status = latest_pnr.get("booking_status") or latest_pnr.get("reservation_status", "Unknown")
            old_status = last_pnr.get("booking_status") or last_pnr.get("reservation_status", "Unknown")
            
            if current_status != old_status:
                alert_details.append(f"PNR status change: {old_status} ➔ {current_status}")
                alert_triggered = True
                if "CNF" in str(current_status).upper():
                    alert_type = "pnr_confirmation"

            # Detect Chart Preparation
            if latest_pnr.get("chart_prepared") and not last_pnr.get("chart_prepared"):
                alert_details.append("Chart has been prepared for your journey. Check your coach assignment.")
                alert_triggered = True
                alert_type = "chart_prepared"

            # Snapshot current PNR status
            booking.last_known_pnr_status = latest_pnr

        # 3. TRIGGER ALERT QUEUING
        if alert_triggered:
            import uuid
            alert_msg = {
                "alert_id": str(uuid.uuid4()),
                "user_id": booking.user_id,
                "booking_id": booking.booking_id,
                "alert_type": alert_type,
                "details": {
                    "message": " | ".join(alert_details),
                    "train_number": booking.train_number,
                    "pnr_number": booking.pnr_number,
                    "timestamp": datetime.utcnow().isoformat()
                },
                "priority": "high" if alert_type in ["cancellation", "pnr_confirmation"] else "normal"
            }
            await self.alert_queue.queue_alert(alert_msg)

    async def _process_booking(self, booking: BookingMonitor, session: AsyncSession):
        """Worker function for a single booking."""
        try:
            logger.debug(f"🔍 Monitoring check for {booking.booking_id}...")
            
            # Fetch from Gateway (L1/L2 Caching is handled inside Gateway)
            live_task = provider_gateway.get_live_status(booking.train_number, booking.travel_date.isoformat())
            
            # PNR can be fetched if number is present
            if booking.pnr_number:
                pnr_task = provider_gateway.get_pnr_status(booking.pnr_number)
            else:
                pnr_task = asyncio.sleep(0, result=None)

            latest_live, latest_pnr = await asyncio.gather(live_task, pnr_task)
            
            # Perform change detection
            await self.detect_changes(booking, latest_live, latest_pnr)
            
            # Update last check mark
            booking.last_check_timestamp = datetime.utcnow()
            
        except Exception as e:
            logger.error(f"Error processing booking {booking.booking_id}: {e}", exc_info=True)

    async def run_scheduler_loop(self, interval_seconds: int = 600):
        """
        Active polling loop.
        Can be registered with the central background task orchestrator.
        """
        self._is_running = True
        logger.info(f"🛰️ Monitoring Scheduler Service Online (Interval: {interval_seconds}s)")
        
        while self._is_running:
            run_start = datetime.utcnow()
            try:
                # Use AsyncSessionUser for user-store queries
                async with AsyncSessionUser() as session:
                    # Fetch candidates
                    bookings = await self.get_bookings_for_monitoring(session)
                    
                    if bookings:
                        logger.info(f"📊 Run active: checking {len(bookings)} bookings.")
                        # Parallel execution for the batch
                        await asyncio.gather(*[self._process_booking(b, session) for b in bookings])
                        # Commit all updates to last_known_status and timestamps
                        await session.commit()
                    else:
                        logger.debug("💤 No monitoring tasks in this run.")
            
            except Exception as e:
                logger.error(f"🆘 Monitoring Scheduler Failure: {e}", exc_info=True)
                await asyncio.sleep(10) # Cooldown on failure

            # Dynamic sleep based on execution time
            elapsed = (datetime.utcnow() - run_start).total_seconds()
            sleep_time = max(10, interval_seconds - elapsed)
            await asyncio.sleep(sleep_time)

# --- Global Orchestration Singleton ---
alert_queue = AlertQueueService()
monitoring_scheduler = BookingMonitorService(alert_queue)

# Hook for application startup
async def start_monitoring_daemon():
    """Entry point to start the background monitoring loop."""
    asyncio.create_task(monitoring_scheduler.run_scheduler_loop())
