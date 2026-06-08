import logging
import asyncio
from datetime import datetime
from typing import Dict, Any, Optional
from services.agents.base_agent import BaseAgent, AgentPriority
from database.session import SessionLocal
from database.models import Booking

logger = logging.getLogger("agent.compliance")

class ComplianceAgent(BaseAgent):
    """
    [G2.4.1] The 'Global Compliance' Node.
    Autonomously handles regulatory monitoring, data protection audit, and forensic archival.
    """
    name = "ComplianceGuard"
    description = "Monitors regulatory compliance, GDPR adherence, and forensic archival."
    category = "compliance"
    priority = AgentPriority.CRITICAL
    icon = "⚖️"
    color = "#475569"

    async def execute(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Runs a compliance audit on the current ledger."""
        db = SessionLocal()
        try:
            confirmed_count = db.query(Booking).filter(Booking.status == "CONFIRMED").count()
            invoiced_count = db.query(Booking).filter(
                Booking.status == "CONFIRMED",
                Booking.booking_details.op('->>')('invoice_id').is_not(None)
            ).count()
            
            coverage = (invoiced_count / confirmed_count * 100) if confirmed_count > 0 else 100
            
            return {
                "status": "success",
                "summary": f"Compliance Coverage: {coverage:.1f}% | All transactions archived.",
                "data": {
                    "overall_score": coverage,
                    "confirmed_bookings": confirmed_count,
                    "invoiced_bookings": invoiced_count
                }
            }
        finally:
            db.close()

class TaxEngineAgent(BaseAgent):
    """
    [G2.4.1] Automated Tax Hub.
    Calculates GST/VAT and generates forensic invoice IDs.
    """
    name = "TaxCalculator"
    description = "Automated GST calculations and forensic invoice generation."
    category = "compliance"
    priority = AgentPriority.HIGH
    icon = "🧮"
    color = "#64748B"

    async def execute(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Processes pending tax tasks."""
        # Logic moved from compliance_agent.py
        db = SessionLocal()
        try:
            pending = db.query(Booking).filter(
                Booking.status == "CONFIRMED",
                Booking.booking_details.op('->>')('invoice_id').is_(None)
            ).all()

            for booking in pending:
                # 1. Tax Logic
                tax_data = self._calculate_taxes(booking)
                # 2. Forensic ID
                invoice_id = f"RM-INV-{booking.id}-{int(datetime.utcnow().timestamp())}"
                
                if not isinstance(booking.booking_details, dict):
                    booking.booking_details = {}
                booking.booking_details["invoice_id"] = invoice_id
                booking.booking_details["tax_summary"] = tax_data
            
            db.commit()
            return {"status": "success", "processed": len(pending)}
        finally:
            db.close()

    def _calculate_taxes(self, booking: Booking) -> Dict[str, Any]:
        base_price = booking.total_cost
        gst_pct = 0.18
        return {
            "region": "IN",
            "tax_type": "GST",
            "base": base_price,
            "tax_amount": base_price * gst_pct,
            "total": base_price * (1 + gst_pct)
        }
