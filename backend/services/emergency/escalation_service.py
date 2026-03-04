import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, Any, List
from api.sos import get_all_sos, _save_event, _load_event
from services.emergency.dispatch_service import dispatch_service
from api.websockets import manager

logger = logging.getLogger(__name__)

class EscalationService:
    def __init__(self):
        self.running = False
        self._task: Optional[asyncio.Task] = None

    async def start(self):
        if self.running: return
        self.running = True
        self._task = asyncio.create_task(self._monitor_loop())
        logger.info("🚀 SOS Escalation Monitor Started")

    async def stop(self):
        self.running = False
        if self._task:
            self._task.cancel()
        logger.info("🛑 SOS Escalation Monitor Stopped")

    async def _monitor_loop(self):
        while self.running:
            try:
                await self.check_all_active_incidents()
                await self.purge_old_incidents() # Task 42
            except Exception as e:
                logger.error(f"Error in escalation monitor: {e}")
            await asyncio.sleep(300) # Check every 5 minutes

    async def purge_old_incidents(self, days: int = 30):
        """
        Task 42: Automated deletion of emergency data after 30 days.
        """
        from api.sos import get_all_sos, _redis, SOS_KEY_PREFIX, SOS_INDEX_KEY
        all_events = await get_all_sos()
        now = datetime.utcnow()
        purge_threshold = now - timedelta(days=days)
        
        purged_count = 0
        for event in all_events:
            triggered_at = datetime.fromisoformat(event.get("triggered_at"))
            if triggered_at < purge_threshold:
                eid = event["id"]
                logger.info(f"♻️ [RETENTION] Purging old incident {eid} (Triggered: {triggered_at})")
                
                # Delete from Redis
                if _redis:
                    try:
                        _redis.delete(f"{SOS_KEY_PREFIX}{eid}")
                        _redis.srem(SOS_INDEX_KEY, eid)
                    except Exception: pass
                
                # Delete from local (if using)
                from api.sos import _local_events
                for i, e in enumerate(_local_events):
                    if e['id'] == eid:
                        _local_events.pop(i)
                        break
                purged_count += 1
        
        if purged_count > 0:
            logger.info(f"✅ [RETENTION] Successfully purged {purged_count} incidents older than {days} days.")

    async def check_all_active_incidents(self):
        """
        Task 38: Monitor unresolved incidents and escalate to HQ if > 60 mins.
        """
        from api.sos import get_all_sos
        all_events = await get_all_sos()
        now = datetime.utcnow()
        
        for event in all_events:
            if event.get("status") in ["active", "responding"]:
                triggered_at = datetime.fromisoformat(event.get("triggered_at"))
                duration_mins = (now - triggered_at).total_seconds() / 60
                
                # If unresolved for more than 60 mins and not yet at escalation level 3
                if duration_mins >= 60 and event.get("escalation_level", 1) < 3:
                    await self.escalate_incident(event)

    async def escalate_incident(self, event: Dict[str, Any]):
        """Perform Level 3 Escalation."""
        event_id = event["id"]
        logger.warning(f"⚠️ [ESCALATION] Incident {event_id} has been active for 60+ mins. Escalating to HQ...")
        
        # 1. Update Event State
        event["escalation_level"] = 3
        event["priority"] = "critical"
        event["extra"] = f"{event.get('extra', '')} | AUTO-ESCALATED TO NATIONAL HQ"
        
        # 2. Dispatch to HQ
        hq_dispatch = await dispatch_service.escalate_to_hq(event)
        event["hq_dispatch"] = hq_dispatch
        
        # 3. Persist & Broadcast
        from api.sos import _save_event
        _save_event(event)
        await manager.broadcast_sos(event)
        
        logger.info(f"✅ [ESCALATION] Incident {event_id} escalated to Level 3.")

escalation_service = EscalationService()
