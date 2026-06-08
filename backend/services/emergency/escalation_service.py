import asyncio
import logging
import os
import shutil
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
import api.safety.sos as sos_api
from services.emergency.dispatch_service import dispatch_service
from api.websockets import manager
from database.session import SessionLocal

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
        # Task 58: Initial startup delay to allow system to stabilize
        # Prevents heavy PII scrubbing immediately on restart
        await asyncio.sleep(15)
        while self.running:
            try:
                await self.check_all_active_incidents()
                await self.purge_old_incidents() # Task 42
            except Exception as e:
                logger.error(f"Error in escalation monitor: {e}")
            await asyncio.sleep(1800) # Check every 30 minutes (Task 42 optimization)

    async def purge_old_incidents(self, days: int = 30):
        """
        Task 42/41: Automated deletion and PII scrubbing.
        Logic: 
        - 24 hours: 'Soft-Scrub' (Clear PII, keep metadata).
        - 30 days: 'Hard-Delete' (Complete removal).
        """
        from api.safety.sos import SOS_KEY_PREFIX, SOS_INDEX_KEY, PNR_REGISTRY_KEY, MEDIA_DIR
        from database.session import SessionLocal
        from database.models import SOSEvent
        import redis
        
        db = SessionLocal()
        all_events = await sos_api.get_all_sos(db)
        now = datetime.utcnow()
        hard_delete_threshold = now - timedelta(days=days)
        soft_scrub_threshold = now - timedelta(hours=24)
        
        # Get Redis connection for cleanup
        try:
            from database.config import Config
            sync_redis = redis.from_url(Config.REDIS_URL)
        except:
            sync_redis = None
        
        purged_count = 0
        scrubbed_count = 0
        
        for event in all_events:
            if not event or not isinstance(event, dict): continue
            
            # Skip if already scrubbed and not old enough for hard delete
            eid = event.get("id")
            if not eid: continue

            try:
                triggered_at_str = event.get("triggered_at")
                if not triggered_at_str: continue
                triggered_at = datetime.fromisoformat(triggered_at_str)
            except (ValueError, TypeError):
                continue

            # 1. Hard Delete (> 30 days) - Task 42
            if triggered_at < hard_delete_threshold:
                logger.info(f"♻️ [HARD DELETE] Decisively wiping all data for incident {eid}")
                
                # A. Redis Cleanup
                if sync_redis:
                    try:
                        sync_redis.delete(f"{SOS_KEY_PREFIX}{eid}")
                        sync_redis.srem(SOS_INDEX_KEY, eid)
                        # Clear PNR registry
                        trip = event.get("trip")
                        if trip and isinstance(trip, dict) and trip.get("pnr_number"):
                            sync_redis.hdel(PNR_REGISTRY_KEY, str(trip.get("pnr_number")))
                    except Exception as e:
                        logger.error(f"Redis cleanup failed for {eid}: {e}")
                
                # B. Media Cleanup (Task 35)
                media_path = os.path.join(MEDIA_DIR, str(eid))
                if os.path.exists(media_path):
                    try:
                        shutil.rmtree(media_path)
                        logger.info(f"🗑️ [MEDIA] Deleted media folder for {eid}")
                    except Exception as e:
                        logger.error(f"Media deletion failed for {eid}: {e}")
                
                # C. Database cleanup (delete SOSEvent record)
                try:
                    sos_record = db.query(SOSEvent).filter(SOSEvent.id == eid).first()
                    if sos_record:
                        db.delete(sos_record)
                except Exception as e:
                    logger.error(f"Database cleanup failed for {eid}: {e}")
                
                purged_count += 1
                
            # 2. Soft Scrub (> 24 hours) - Task 41
            elif triggered_at < soft_scrub_threshold:
                if event.get("privacy_status") == "scrubbed":
                    continue # Already done, skip noise
                
                logger.info(f"🛡️ [SOFT SCRUB] Redacting PII for incident {eid}")
                import hashlib
                
                # Pseudonymize
                if event.get("phone"):
                    event["phone"] = hashlib.sha256(event["phone"].encode()).hexdigest()[:12]
                event["name"] = "ANONYMOUS_USER"
                
                # Clear sensitive history
                event["chat_history"] = []
                event["location_history"] = []
                event["extra"] = "[DATA_REDACTED_FOR_PRIVACY]"
                event["privacy_status"] = "scrubbed"
                
                await sos_api._save_event_async(event, db)
                scrubbed_count += 1
        
        try:
            db.commit()
        except:
            db.rollback()
        finally:
            db.close()
        
        if purged_count > 0 or scrubbed_count > 0:
            logger.info(f"✅ [PRIVACY] Scoped operations: Hard-deleted {purged_count}, Soft-scrubbed {scrubbed_count}.")

    async def check_all_active_incidents(self):
        """
        Task 38: Dynamic Escalation Profiler.
        Calculates timeout based on Time, Priority, and Category.
        """
        all_events = await sos_api.get_all_sos()
        now = datetime.utcnow()
        
        for event in all_events:
            if event.get("status") in ["active", "responding"]:
                # Task 38: Multi-factor timeout calculation
                timeout_mins = 60 # Base
                
                # 1. Night Bias (Task 26)
                is_night = now.hour >= 23 or now.hour <= 4
                if is_night: timeout_mins -= 40
                
                # 2. Category Speedup
                cat = event.get("category", "unknown")
                if cat == "fire": timeout_mins -= 45
                elif cat in ["medical", "medical_emergency_fall"]: timeout_mins -= 30
                elif cat == "security": timeout_mins -= 20
                
                # 3. Priority Floor
                if event.get("priority") == "critical": timeout_mins = min(timeout_mins, 10)
                
                # Final Floor
                timeout_mins = max(timeout_mins, 5)
                
                triggered_at = datetime.fromisoformat(event.get("triggered_at"))
                duration_mins = (now - triggered_at).total_seconds() / 60
                
                if duration_mins >= timeout_mins and event.get("escalation_level", 1) < 3:
                    logger.warning(f"🚀 [DYNAMIC ESCALATION] Escalating {event['id']} (Cat: {cat}) after {round(duration_mins, 1)}m (Timeout: {timeout_mins}m)")
                    await self.escalate_incident(event)

    async def escalate_incident(self, event: Dict[str, Any]):
        """Perform Level 3 Escalation with AI Summary (Task 57)."""
        if not event or not isinstance(event, dict):
            logger.error("Cannot escalate null or invalid event object.")
            return

        event_id = event.get("id")
        logger.warning(f"⚠️ [ESCALATION] Incident {event_id} has been active for 60+ mins. Escalating to HQ...")
        
        # 1. Update Event State
        event["escalation_level"] = 3
        event["priority"] = "critical"
        
        # Task 57: Generate Brief for HQ
        try:
            from utils.summarizer import ai_summarizer
            event["hq_summary"] = ai_summarizer.generate_summary(event)
        except Exception as e:
            logger.error(f"Summarizer failed: {e}")
            event["hq_summary"] = "Manual intervention required."
        
        event["extra"] = f"{event.get('extra', '')} | AUTO-ESCALATED TO NATIONAL HQ | SUMMARY: {event.get('hq_summary')}"
        
        # 2. Dispatch to HQ
        try:
            hq_dispatch = await dispatch_service.escalate_to_hq(event)
            event["hq_dispatch"] = hq_dispatch
        except Exception as e:
            logger.error(f"HQ Dispatch failed: {e}")
        
        # 3. Persist & Broadcast
        try:
            db = SessionLocal()
            await sos_api._save_event_async(event, db)
            db.commit()
            db.close()
            await manager.broadcast_sos(event)
            logger.info(f"✅ [ESCALATION] Incident {event_id} escalated to Level 3.")
        except Exception as e:
            logger.error(f"Failed to persist/broadcast escalation: {e}")

escalation_service = EscalationService()
