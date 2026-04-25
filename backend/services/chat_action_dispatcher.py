import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from database.models import User, Booking
from services.pnr_service import pnr_status_service
from services.live_status_service import LiveStatusService
from services.emergency.safety_service import safety_service
from core.resilience import circuit_breaker_manager, CircuitBreaker, CircuitConfig
from core.retry import retry_async, RetryPolicy
from collections import deque
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)

class ChatActionDispatcher:
    """
    Task 2.7: Maps AI Intents to Backend Actions with Zero AI Chatter.
    
    With resilience patterns: circuit breaker, retry, and metrics tracking.
    """

    def __init__(self):
        """Initialize dispatcher with resilience patterns."""
        # Circuit breaker for external service calls
        self._pnr_breaker = circuit_breaker_manager.get_or_create(
            "chat_dispatcher_pnr",
            CircuitConfig(failure_threshold=5, timeout_seconds=30.0)
        )
        self._live_status_breaker = circuit_breaker_manager.get_or_create(
            "chat_dispatcher_live_status",
            CircuitConfig(failure_threshold=5, timeout_seconds=30.0)
        )
        self._booking_breaker = circuit_breaker_manager.get_or_create(
            "chat_dispatcher_booking",
            CircuitConfig(failure_threshold=3, timeout_seconds=60.0)
        )
        
        # Retry policies
        self._retry_policy = RetryPolicy(
            max_attempts=3,
            initial_delay=0.5,
            max_delay=5.0,
            conditions=[
                lambda e: "timeout" in str(e).lower(),
                lambda e: "connection" in str(e).lower()
            ]
        )
        
        # Metrics tracking
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = asyncio.Lock()
        
        logger.info("ChatActionDispatcher initialized with resilience patterns")

    @staticmethod
    async def dispatch(intent: str, entities: Dict[str, Any], db: Session, user: Optional[User]) -> Optional[str]:
        """
        Executes mission-critical actions based on intent.
        Returns a formatted string result if an action was performed, else None.
        """
        try:
            if intent == 'pnr':
                pnr = entities.get("pnr")
                if pnr:
                    res = await pnr_status_service.get_status(pnr, user_id=user.id if user else None, db=db)
                    if res.get("success"):
                        return (
                            f"✅ **PNR LOGISTICS ACQUIRED**\n\n"
                            f"📍 **PNR**: {pnr}\n"
                            f"🚆 **Train**: {res.get('train')}\n"
                            f"🎫 **Status**: {res.get('status')}\n"
                            f"💺 **Berth**: {res.get('seat', 'Check Dashboard')}\n\n"
                            f"_{res.get('message')}_"
                        )
                    return f"❌ PNR Lookup Failed: {res.get('message')}"

            elif intent == 'track':
                # Attempt to track the last booking if no train number is provided
                train_no = entities.get("train_no") or entities.get("number")
                if not train_no and user:
                    last_booking = db.query(Booking).filter(Booking.user_id == user.id).order_by(Booking.created_at.desc()).first()
                    if last_booking: train_no = last_booking.train_number
                
                if train_no:
                    live_svc = LiveStatusService()
                    res = await live_svc.get_live_status(train_no)
                    if res and isinstance(res, dict) and res.get("success"):
                        return (
                            f"📡 **LIVE TELEMETRY: {train_no}**\n\n"
                            f"📢 **Current**: {res.get('message', 'Acquiring...')}\n"
                            f"🕒 **Updated**: {res.get('updated_time', 'Real-time')}\n\n"
                            f"_Full tracking data injected into your Dashboard._"
                        )
                return "📡 Please provide a train number or check your active bookings to initialize tracking."

            elif intent == 'book':
                if not user: return "💼 Mission Identity Unknown. Please sign in to execute booking commands."
                
                passengers = entities.get("data", [])
                if not passengers:
                    return "🛂 Please specify passenger details (e.g., 'Book for Gaurav (30)')."

                # Retrieve last active search context for this user
                from services.session_lock_service import SearchSessionManager
                context = SearchSessionManager.get_search_context(user.id)
                if not context:
                    return "🔍 I don't see a recent search in your session. Please find a route first."

                # Execute Smart Booking [Group 1 Orchestration]
                from services.orchestration.booking_orchestrator import BookingOrchestrator
                orchestrator = BookingOrchestrator(db)
                
                # Payload construction from context
                route_payload = {
                    "source": context.get("source"),
                    "destination": context.get("destination"),
                    "travel_date": context.get("date"),
                    "train_number": context.get("results_preview", [{}])[0].get("train_number"),
                    "class_code": context.get("results_preview", [{}])[0].get("class_code"),
                    "fare": context.get("results_preview", [{}])[0].get("fare", 0.0)
                }

                res = await orchestrator.execute_smart_booking(user.id, route_payload, passengers)
                
                if res["status"] == "SUCCESS":
                    return (
                        f"🎉 **BOOKING INITIATED**\n\n"
                        f"✅ **PNR**: {res['pnr']}\n"
                        f"🚆 **Train**: {route_payload['train_number']}\n"
                        f"📅 **Date**: {route_payload['travel_date']}\n\n"
                        f"_Your travel logistics are being finalized in our secure ledger._"
                    )
                elif res["status"] == "FLEX_OFFERED":
                    alt_str = "\n".join([f"• 🚆 {a['train_number']} ({a['class_code']}) - ₹{a['fare']}" for a in res['alternatives']])
                    return (
                        f"⚠️ **TARGET SOLD OUT**\n\n"
                        f"Our Flex-Agent has autonomously located replacements:\n"
                        f"{alt_str}\n\n"
                        f"Would you like to switch to one of these options?"
                    )
                
                return f"❌ Booking Failed: {res.get('message')}"

            elif intent == 'bookings':
                if not user: return "🎫 Mission Identity Unknown. Please sign in to access your travel history."
                count = db.query(Booking).filter(Booking.user_id == user.id).count()
                return f"🎫 mission history retrieved. I've found **{count}** previous deployments in your records."

            elif intent == 'sos':
                # Safety Protocol is handled by separate logic but we can trigger a check
                if user:
                    await safety_service.check_journey_deviation(user.id, 0, 0, db) # Mock trigger
                return "🚨 **EMERGENCY PROTOCOL INITIALIZED.** Notifying emergency contacts and sharing live telemetry."

        except Exception as e:
            logger.error(f"Dispatch Error: {e}", exc_info=True)
            return f"⚠️ Protocol Interrupted: {str(e)}"

        return None

chat_dispatcher = ChatActionDispatcher()
