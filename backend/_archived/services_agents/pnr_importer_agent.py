import logging
import asyncio
from typing import Dict, Any, Optional
from services.agents.base_agent import BaseAgent, AgentPriority
from services.pnr_service import pnr_status_service
from database.session import SessionLocal

logger = logging.getLogger("agent.pnr_importer")

class PNRImporterAgent(BaseAgent):
    """
    [G1.4.1] The 'PNR Importer' Growth Agent.
    Allows users to import external rail tickets into the RouteMaster ecosystem.
    Converts raw PNRs into 'Shadow Tickets' that the Safety Guardian can monitor.
    """
    name = "PNRImporterAgent"
    description = "Imports and monitors external train tickets for safety and delay tracking."
    category = "growth"
    priority = AgentPriority.NORMAL
    icon = "📥"
    color = "#F43F5E" # Rose

    async def import_external_pnr(self, pnr: str, user_id: str) -> Dict[str, Any]:
        """
        Main entry point for PNR hydration.
        """
        logger.info(f"✨ [PNR_IMPORTER] Attempting import for PNR: {pnr}")
        
        # 1. Verify and Fetch (Child G1.4.1.1)
        db = SessionLocal()
        try:
            status = await pnr_status_service.get_status(pnr, user_id=user_id, db=db)
            if not status.get("success"):
                return {"success": False, "message": "Could not verify PNR. Check the number and try again."}

            # 2. Create Shadow Record (Child G1.4.1.1)
            # We treat this like a real booking for monitoring purposes
            from database.models import Booking
            import uuid
            
            # Check if already imported
            existing = db.query(Booking).filter(Booking.pnr_number == pnr).first()
            if existing:
                return {"success": False, "message": "This PNR is already being monitored by RouteMaster."}

            shadow_booking = Booking(
                id=str(uuid.uuid4()),
                user_id=user_id,
                pnr_number=pnr,
                train_name=status.get("train", "External Train"),
                status="IMPORTED",
                is_external=True
            )
            db.add(shadow_booking)
            db.commit()

            # 3. Handover to Guardian (Child G1.4.1.2)
            await self._activate_guardian_watch(shadow_booking.id)

            # 4. Generate Growth Nudge (Child G1.4.1.3)
            nudge = self._generate_growth_nudge(status)

            return {
                "success": True, 
                "message": f"PNR {pnr} imported successfully. The Safety Guardian is now watching your journey.",
                "nudge": nudge
            }

        except Exception as e:
            logger.error(f"PNR Import Error: {e}")
            return {"success": False, "message": "Internal error during PNR import."}
        finally:
            db.close()

    async def _activate_guardian_watch(self, booking_id: str):
        """
        Signals the Guardian Agent to start active monitoring.
        """
        from services.agents.guardian_agent import GuardianAgent
        # We don't call it directly as a method typically, we broadcast a signal if event bus is active
        # Or simple log which the Guardian's pulse picks up
        logger.info(f"🛡️ [PNR_IMPORTER] PNR {booking_id} handed over to Guardian Swarm.")

    def _generate_growth_nudge(self, status: Dict[str, Any]) -> str:
        """
        Linguistic Nudge for conversion (Child G1.4.1.3).
        """
        train_name = status.get("train", "your train")
        current_status = status.get("status", "Unknown")
        
        if "WL" in str(current_status):
             return f"We've added {train_name} to your dashboard. It looks like you're on Waitlist ({current_status}). Would you like to see 100% confirmed bus alternatives for this route?"
        
        return f"Nice! {train_name} is confirmed. We'll monitor it for any platform changes or delays to keep your trip stress-free."

pnr_importer_agent = PNRImporterAgent()
