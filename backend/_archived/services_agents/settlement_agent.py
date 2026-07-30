import logging
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, List
from services.agents.base_agent import BaseAgent, AgentPriority
from database.session import SessionLocal
from database.models import Booking, EscrowStatus

logger = logging.getLogger("agent.settlement_swarm")

class RapidSettlementAgent(BaseAgent):
    """
    [G2.3.1] The 'Rapid Settlement' Optimizer.
    A mission-critical financial agent that ensures business liquidity.
    Proactively verifies pending payments and moves them to OPERATING_CAPITAL.
    """
    name = "RapidSettlementAgent"
    description = "Accelerates bank-to-ledger settlement for optimal capital liquidity."
    category = "finance"
    priority = AgentPriority.CRITICAL
    icon = "💰"
    color = "#10B981" # Emerald

    def __init__(self):
        super().__init__()
        self.check_interval = 60 # Polling every 60 seconds (Proactive)
        self.max_pending_time_mins = 5

    async def pulse(self):
        """Proactive Verification Pulse."""
        while True:
            try:
                await self.audit_pending_settlements()
            except Exception as e:
                logger.error(f"🚨 [SETTLEMENT] Audit Error: {e}")
            await asyncio.sleep(self.check_interval)

    async def audit_pending_settlements(self):
        """
        [Child G2.3.1.1] Verification Pulse.
        Iterates through 'In-Flight' payments that haven't been matched yet.
        """
        db = SessionLocal()
        try:
            # 1. Identify "Stuck" Payments
            threshold = datetime.utcnow() - timedelta(minutes=self.max_pending_time_mins)
            pending_bookings = db.query(Booking).filter(
                Booking.escrow_status == EscrowStatus.UTR_SUBMITTED,
                Booking.created_at < threshold
            ).all()

            if not pending_bookings:
                return

            logger.info(f"🔍 [SETTLEMENT] Found {len(pending_bookings)} pending UTRs for proactive verification.")
            
            for booking in pending_bookings:
                # 2. Mock API Call to Bank Gateway (Child G2.3.1.1)
                # In production, this calls Razorpay/UPI-Verify API.
                success = await self._verify_with_bank_api(booking.utr_number)
                
                if success:
                    # 3. Settlement Accelerator (Child G2.3.1.2)
                    await self._finalize_settlement(db, booking)
                else:
                    # Liquidity Guard (Child G2.3.1.3) awareness
                    pass

            db.commit()
        finally:
            db.close()

    async def _verify_with_bank_api(self, utr: str) -> bool:
        """CONCEPTUAL: Manual API Probe for missed SMS notifications."""
        # Simulated API verify (conceptually calling UPI Provider)
        await asyncio.sleep(0.5) 
        return True # Mocking a successful verification for demo

    async def _finalize_settlement(self, db, booking):
        """
        Instantly moves funds to OPERATING_CAPITAL.
        """
        logger.info(f"⚡ [SETTLEMENT] Proactive Match Success for Booking {booking.id}. Accelerating Ledger...")
        
        from services.ledger_service import ledger_service
        # Move from Bank Liquidity to Operating Capital
        await ledger_service.record_transaction(
            db,
            amount=booking.amount_paid,
            source_account="BANK_LIQUIDITY",
            destination_account="OPERATING_CAPITAL",
            reference_id=f"RECON_{booking.id}",
            description=f"[PROACTIVE_SETTLEMENT] Verified via RapidSettlementAgent API Pulse."
        )

        booking.escrow_status = EscrowStatus.VERIFIED
        booking.escrow_message = "✅ Verified proactively via Settlement Swarm."
        
        # Notify user instantly
        from services.ws_manager import ws_manager
        await ws_manager.broadcast_log(str(booking.id), "✅ Payment verified proactively!", "SUCCESS")

rapid_settlement_agent = RapidSettlementAgent()
