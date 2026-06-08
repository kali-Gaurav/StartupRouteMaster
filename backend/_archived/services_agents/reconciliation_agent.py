import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any
from services.agents.base_agent import BaseAgent, AgentPriority
from database.session import SessionLocal
from database.models import Booking

logger = logging.getLogger("agent.reconciliation")

class ProviderReconciliationAgent(BaseAgent):
    """
    [G1.5.1] The 'Provider Reconciliation' Auditor.
    Ensures absolute parity between RouteMaster and Upstream Providers (Rail/Bus).
    Detects and fixes 'Ghost Bookings' autonomously.
    """
    name = "ProviderReconciliationAgent"
    description = "Synchronizes internal booking states with external provider APIs."
    category = "operations"
    priority = AgentPriority.HIGH
    icon = "🔄"
    color = "#F59E0B" # Amber

    async def pulse(self):
        """Continuous Parity Pulse."""
        while True:
            try:
                await self.audit_provider_parity()
            except Exception as e:
                logger.error(f"🚨 [RECON] Audit Failure: {e}")
            await asyncio.sleep(900) # Every 15 minutes

    async def audit_provider_parity(self):
        """
        [Child G1.5.1.1] Parity Engine.
        Scans recently confirmed/failed bookings and verifies with the source.
        """
        db = SessionLocal()
        try:
            # Check bookings from last 6 hours
            lookback = datetime.utcnow() - timedelta(hours=6)
            bookings = db.query(Booking).filter(Booking.created_at >= lookback).all()
            
            logger.info(f"🔍 [RECON] Auditing {len(bookings)} bookings for provider parity...")
            
            drift_count = 0
            for booking in bookings:
                # 1. Fetch Real Status from Provider (Child G1.5.1.1)
                provider_status = await self._fetch_upstream_status(booking)
                
                # 2. Parity Comparison
                if booking.status == "CONFIRMED" and provider_status == "FAILED":
                    await self._reap_ghost_booking(db, booking, "FAILED_AT_SOURCE")
                    drift_count += 1
                elif booking.status == "FAILED" and provider_status == "CONFIRMED":
                    await self._rescue_ghost_booking(db, booking)
                    drift_count += 1
            
            # 3. Drift Alerting (Child G1.5.1.3)
            if len(bookings) > 0 and (drift_count / len(bookings)) > 0.05:
                logger.critical(f"🛑 [RECON] CRITICAL DRIFT DETECTED: {(drift_count/len(bookings))*100}% of bookings out of sync!")
            
            db.commit()
        finally:
            db.close()

    async def _fetch_upstream_status(self, booking: Booking) -> str:
        """Mocked upstream API call (e.g. IRCTC/RedBus)."""
        # In production: resp = await provider_api.get_pnr_status(booking.pnr_number)
        return booking.status # Simulated parity for now

    async def _reap_ghost_booking(self, db, booking, reason):
        """
        [Child G1.5.1.2] Autonomous Remediation (Refund).
        """
        logger.warning(f"👻 [RECON] Reaping Ghost Booking {booking.id}: Internal Confirmed, but Provider Failed.")
        booking.status = "FAILED_SYNC"
        if not isinstance(booking.booking_details, dict):
            booking.booking_details = {}
        booking.booking_details["recon_failure"] = reason
        
        # Trigger Auto-Refund
        from services.agents.bailiff_agent import bailiff_agent
        # Bailiff handles the VOID/Refund logic we built in G2.1.1
        await bailiff_agent.void_and_notify(booking.user_id, booking.id, "Provider Denied Reservation")

    async def _rescue_ghost_booking(self, db, booking):
        """
        [Child G1.5.1.2] Autonomous Remediation (Rescue).
        """
        logger.info(f"🩹 [RECON] Rescuing Ghost Booking {booking.id}: Internal Failed, but Provider Confirmed!")
        booking.status = "CONFIRMED"
        # Trigger fulfillment notification
        from services.ws_manager import ws_manager
        await ws_manager.send_to_user(booking.user_id, {"type": "BOOKING_RESCUED", "pnr": booking.pnr_number}, "SUCCESS")

reconciliation_agent = ProviderReconciliationAgent()
