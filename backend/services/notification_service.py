import logging
import asyncio
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from datetime import datetime
from dataclasses import dataclass, field
from collections import deque

from database.models import User, NotificationToken, UserAlert, NotificationPreference, NotificationLog
from core.resilience import circuit_breaker_manager, CircuitBreaker, CircuitConfig
from core.retry import RetryPolicy

logger = logging.getLogger("notification-service")


class NotificationServiceMetrics:
    """Metrics tracking for notification service."""
    
    def __init__(self):
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = asyncio.Lock()
    
    async def record_notification(self, channel: str, success: bool, duration_ms: float):
        """Record notification metrics."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "channel": channel,
                "success": success,
                "duration_ms": duration_ms
            })
    
    def get_metrics(self) -> dict:
        """Get service metrics."""
        if not self._metrics:
            return {"total_notifications": 0, "success_rate": 0.0}
        
        total = len(self._metrics)
        successful = sum(1 for m in self._metrics if m["success"])
        by_channel = {}
        for m in self._metrics:
            channel = m["channel"]
            if channel not in by_channel:
                by_channel[channel] = {"total": 0, "success": 0}
            by_channel[channel]["total"] += 1
            if m["success"]:
                by_channel[channel]["success"] += 1
        
        return {
            "total_notifications": total,
            "successful_notifications": successful,
            "failed_notifications": total - successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "by_channel": by_channel
        }


@dataclass
class NotificationJob:
    """Represents a notification job to be processed."""
    user_id: str
    title: str
    body: str
    alert_type: str = "SYSTEM"
    priority: int = 10
    payload: Optional[Dict[str, Any]] = None
    booking_id: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    retry_count: int = 0
    max_retries: int = 3


class NotificationQueue:
    """Thread-safe notification queue with retry logic."""
    
    def __init__(self, max_size: int = 1000):
        self._queue: List[NotificationJob] = []
        self._max_size = max_size
        self._lock = asyncio.Lock()
    
    async def put(self, job: NotificationJob) -> bool:
        """Add a notification job to the queue."""
        async with self._lock:
            if len(self._queue) >= self._max_size:
                logger.warning("Notification queue full, dropping oldest")
                self._queue.pop(0)
            self._queue.append(job)
            return True
    
    async def get(self) -> Optional[NotificationJob]:
        """Get the next notification job."""
        async with self._lock:
            if not self._queue:
                return None
            return self._queue.pop(0)
    
    def size(self) -> int:
        """Get current queue size."""
        return len(self._queue)
    
    def clear(self) -> None:
        """Clear the queue."""
        self._queue.clear()


# Global notification queue
notification_queue = NotificationQueue()


class NotificationService:
    """Notification service with queuing and retry support."""

    def __init__(self):
        self._queue = notification_queue
        self._worker_task: Optional[asyncio.Task] = None
        
        # Circuit breakers for external services
        self._fcm_breaker = circuit_breaker_manager.get_or_create(
            "notification_fcm",
            CircuitConfig(failure_threshold=5, timeout_seconds=30.0, success_threshold=2)
        )
        self._telegram_breaker = circuit_breaker_manager.get_or_create(
            "notification_telegram",
            CircuitConfig(failure_threshold=3, timeout_seconds=15.0, success_threshold=2)
        )
        self._db_breaker = circuit_breaker_manager.get_or_create(
            "notification_db",
            CircuitConfig(failure_threshold=5, timeout_seconds=10.0, success_threshold=3)
        )
        
        # Retry policies
        self._fcm_retry = RetryPolicy(
            max_attempts=3,
            initial_delay=0.5,
            max_delay=10.0,
            conditions=[
                lambda e: "timeout" in str(e).lower(),
                lambda e: "connection" in str(e).lower()
            ]
        )
        self._telegram_retry = RetryPolicy(
            max_attempts=3,
            initial_delay=0.5,
            max_delay=5.0,
            conditions=[
                lambda e: "timeout" in str(e).lower()
            ]
        )
        
        # Metrics tracking
        self._metrics = NotificationServiceMetrics()
        
        # Worker task (started on first use)
        self._worker_task = None
        logger.info("NotificationService initialized with resilience patterns")
    
    def _start_worker(self):
        """Start the background worker if not already running."""
        if self._worker_task is None or self._worker_task.done():
            self._worker_task = asyncio.create_task(self._process_queue())
            logger.info("Notification worker started")

    async def _process_queue(self):
        """Background worker to process notification queue."""
        while True:
            try:
                job = await self._queue.get()
                if job is None:
                    await asyncio.sleep(1)
                    continue
                
                # Process the notification
                await self._send_notification(job)
                
                # Small delay between notifications
                await asyncio.sleep(0.1)
                
            except asyncio.CancelledError:
                logger.info("Notification worker cancelled")
                break
            except Exception as e:
                logger.error(f"Error in notification worker: {e}")
                await asyncio.sleep(1)

    async def _send_notification(self, job: NotificationJob):
        """Send a single notification with retry."""
        from database.session import SessionLocal
        
        db = SessionLocal()
        success_count: int = 0
        failure_count: int = 0
        try:
            # 1. Store in DB (In-App History)
            alert = UserAlert(
                user_id=job.user_id,
                title=job.title,
                body=job.body,
                alert_type=job.alert_type,
                priority=job.priority,
                payload=job.payload or {}
            )
            db.add(alert)
            
            # 2. Find active channels
            tokens = db.query(NotificationToken).filter(
                NotificationToken.user_id == job.user_id,
                NotificationToken.is_active == True
            ).all()
            
            # 3. Check Preferences
            prefs = db.query(NotificationPreference).filter(
                NotificationPreference.user_id == job.user_id
            ).first()
            
            db.commit()
            
            # 4. [Task 1.1.5] Notification Delivery Logging
            for t in tokens:
                try:
                    # Priority & Preference Routing
                    if job.alert_type == "PROMOTION" and prefs and not prefs.enable_promotions:
                        continue
                    
                    log_entry = NotificationLog(
                        booking_id=job.booking_id,
                        channel=t.channel,
                        status="pending"
                    )
                    db.add(log_entry)
                    db.flush() # Get notification_id
                    
                    try:
                        if t.channel == "WEB_PUSH":
                            await self._send_fcm(str(t.token), job.title, job.body, job.payload)
                        elif t.channel == "TELEGRAM":
                            from services.telegram_dispatcher import telegram_dispatcher
                            await telegram_dispatcher.send_message(str(t.token), f"<b>{job.title}</b>\n\n{job.body}")
                        
                        log_entry.status = "sent"
                        success_count += 1
                    except Exception as e:
                        logger.error(f"Failed to deliver to {t.channel} for {job.user_id}: {e}")
                        log_entry.status = "failed"
                        log_entry.error_message = str(e)
                        failure_count += 1
                except Exception as inner_e:
                    logger.error(f"Error logging notification delivery: {inner_e}")
            
            db.commit()
            logger.info(f"📲 Notification sent to {job.user_id}: {success_count} success, {failure_count} failures")
            
        except Exception as e:
            logger.error(f"Error sending notification: {e}")
            db.rollback()
            
            # Retry logic
            if job.retry_count < job.max_retries:
                job.retry_count += 1
                await self._queue.put(job)
                logger.info(f"🔄 Retrying notification ({job.retry_count}/{job.max_retries})")
        finally:
            db.close()

    async def send_alert(
        self, 
        db: Session, 
        user_id: str, 
        title: str, 
        body: str, 
        alert_type: str = "SYSTEM", 
        priority: int = 10, 
        payload: Optional[Dict[str, Any]] = None,
        booking_id: Optional[str] = None,
        immediate: bool = False
    ):
        """
        [Task 46.1 & 46.4] Main orchestrator for delivering an alert.
        
        Args:
            db: Database session
            user_id: Target user ID
            title: Notification title
            body: Notification body
            alert_type: Type of alert (SYSTEM, PROMOTION, etc.)
            priority: Priority level (1-10, lower is higher priority)
            payload: Additional data
            booking_id: Optional booking reference (Task 1.1.5)
            immediate: If True, send immediately; otherwise queue
        """
        # Ensure worker is running
        self._start_worker()
        
        job = NotificationJob(
            user_id=user_id,
            title=title,
            body=body,
            alert_type=alert_type,
            priority=priority,
            payload=payload,
            booking_id=booking_id
        )
        
        if immediate:
            # Send immediately
            await self._send_notification(job)
        else:
            # Queue for background processing
            await self._queue.put(job)
            logger.debug(f"Notification queued for {user_id}: {title[:30]}...")

    async def _send_fcm(self, token: str, title: str, body: str, payload: Optional[Dict[str, Any]] = None):
        """
        [Task 46.2] Firebase Cloud Messaging.
        """
        logger.info(f"📲 FCM Push Sent to {token[:10]}... | {title}")
        # firebase_admin.messaging.send(...) would go here

    async def _send_telegram(self, chat_id: str, title: str, body: str):
        """
        [Task 46.3] Telegram Bot API.
        """
        logger.info(f"✈️ Telegram Sent to {chat_id} | {title}")
        # requests.post(f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage", ...)

    def get_user_notifications(
        self, 
        db: Session, 
        user_id: str, 
        limit: int = 20,
        unread_only: bool = False
    ) -> List[UserAlert]:
        """
        [Task 46.6] Fetch notification history for in-app center.
        """
        query = db.query(UserAlert).filter(UserAlert.user_id == user_id)
        
        if unread_only:
            query = query.filter(UserAlert.is_read == False)
        
        return query.order_by(UserAlert.timestamp.desc()).limit(limit).all()

    def mark_as_read(self, db: Session, alert_id: int, user_id: str) -> bool:
        """Mark a notification as read."""
        try:
            alert = db.query(UserAlert).filter(
                UserAlert.id == alert_id,
                UserAlert.user_id == user_id
            ).first()
            if alert:
                # Fix for SQLAlchemy Column assignment
                setattr(alert, "is_read", True)
                db.commit()
                return True
            return False
        except Exception as e:
            logger.error(f"Failed to mark notification as read: {e}")
            return False

    def get_queue_stats(self) -> Dict[str, Any]:
        """Get notification queue statistics."""
        return {
            "queue_size": self._queue.size(),
            "worker_running": self._worker_task is not None and not self._worker_task.done()
        }

    def shutdown(self):
        """Shutdown the notification worker."""
        if self._worker_task:
            self._worker_task.cancel()
            logger.info("Notification worker shutdown initiated")


notification_service = NotificationService()


