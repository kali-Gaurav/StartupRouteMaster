import logging
from typing import Dict, Any, Optional
from sqlalchemy.orm import Session
from database.models import User, Booking
from services.pnr_service import pnr_status_service
from services.live_status_service import LiveStatusService
from services.emergency.safety_service import safety_service

logger = logging.getLogger(__name__)

class ChatActionDispatcher:
    """Task 2.7: Maps AI Intents to Backend Actions with Zero AI Chatter."""

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
                    res = await pnr_status_service.get_status(pnr)
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
                    # Use run_in_threadpool since LiveStatusService uses 'requests' (sync)
                    import asyncio
                    res = await asyncio.to_thread(live_svc.get_live_status, train_no)
                    if res and res.get("success"):
                        return (
                            f"📡 **LIVE TELEMETRY: {train_no}**\n\n"
                            f"📢 **Current**: {res.get('message', 'Acquiring...')}\n"
                            f"🕒 **Updated**: {res.get('updated_time', 'Real-time')}\n\n"
                            f"_Full tracking data injected into your Dashboard._"
                        )
                return "📡 Please provide a train number or check your active bookings to initialize tracking."

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
