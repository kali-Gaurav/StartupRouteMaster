import logging
import math
import io
import csv
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from collections import deque

logger = logging.getLogger(__name__)

class TaxEngineService:
    """
    Task 5: Platform Fee & GST Engine.
    Calculates dynamic fees and GST on service components.
    
    With metrics tracking for tax calculation operations.
    """
    
    GST_RATE = 0.18 # 18% GST on platform fee
    
    # Task 5.9: Multi-currency architecture (internal rates)
    EXCHANGE_RATES = {
        "USD": 83.50,
        "EUR": 90.10,
        "GBP": 105.20,
        "INR": 1.00
    }
    
    def __init__(self):
        """Initialize tax engine with metrics tracking."""
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = __import__('threading').Lock()
        
        logger.info("TaxEngineService initialized with metrics tracking")
    
    def _record_metrics(self, operation_type: str, success: bool, error: str = None):
        """Record metrics for tax calculation operations."""
        with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "operation_type": operation_type,
                "success": success,
                "error": error
            })
    
    def get_metrics(self) -> dict:
        """Get service metrics."""
        if not self._metrics:
            return {"total_operations": 0, "success_rate": 0.0}
        
        total = len(self._metrics)
        successful = sum(1 for m in self._metrics if m["success"])
        by_type = {}
        for m in self._metrics:
            op_type = m.get("operation_type", "unknown")
            if op_type not in by_type:
                by_type[op_type] = {"total": 0, "success": 0}
            by_type[op_type]["total"] += 1
            if m["success"]:
                by_type[op_type]["success"] += 1
        
        return {
            "total_operations": total,
            "successful_operations": successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "operation_breakdown": by_type
        }
    
    def health_check(self) -> dict:
        """Health check endpoint."""
        return {
            "status": "healthy",
            "gst_rate": self.GST_RATE,
            "metrics": self.get_metrics()
        }
    
    def convert_currency(self, amount_inr: float, target_currency: str) -> float:
        """Internal conversion for display purposes."""
        rate = self.EXCHANGE_RATES.get(target_currency.upper(), 1.0)
        return round(amount_inr / rate, 2)
    
    def is_first_time_user(self, db: Session, user_id: str) -> bool:
        """Task 5.7: Zero-fee toggle for First Time Users."""
        from database.models import Booking
        if not db or not user_id:
            return False
        count = db.query(Booking).filter(Booking.user_id == user_id).count()
        return count == 0

    def calculate_breakdown(self, base_fare: float, discount_code: Optional[str] = None, is_first_time: bool = False, display_currency: str = "INR") -> Dict[str, Any]:
        """
        Task 5.1: Dynamic fee calculation based on ticket value.
        Task 5.3: GST (18%) auto-calculation on the Service Fee component.
        """
        # Dynamic Fee: 2% of base fare with a minimum of ₹20 and maximum of ₹150
        platform_fee_base = max(20.0, min(base_fare * 0.02, 150.0))
        
        discount_amount = 0.0
        # 5.6 Support for "Discount Codes"
        if discount_code == "FIRSTFREE":
            discount_amount = platform_fee_base
            logger.info("Applying FIRSTFREE discount: Platform fee waived.")
            
        # 5.7 Zero-fee toggle for "First Time Users"
        if is_first_time and discount_amount == 0.0:
            discount_amount = platform_fee_base
            logger.info("First Time User detected: Platform fee waived automatically.")
        
        platform_fee_final = max(0.0, platform_fee_base - discount_amount)
        
        # GST only on the platform fee
        gst_amount = platform_fee_final * self.GST_RATE
        
        # Total before rounding
        raw_total = base_fare + platform_fee_final + gst_amount
        
        # 5.8 Round-off logic to the nearest rupee
        total_rounded = math.ceil(raw_total)
        round_off = total_rounded - raw_total
        
        breakdown = {
            "base_fare": round(base_fare, 2),
            "platform_fee": round(platform_fee_final, 2),
            "gst": round(gst_amount, 2),
            "round_off": round(round_off, 2),
            "total": float(total_rounded),
            "currency": "INR",
            "gst_rate": f"{self.GST_RATE * 100}%"
        }
        
        # 5.9 Add display currency conversion if requested
        if display_currency != "INR":
            breakdown["display_total"] = self.convert_currency(breakdown["total"], display_currency)
            breakdown["display_currency"] = display_currency
            
        logger.debug(f"Calculated breakdown: {breakdown}")
        return breakdown

    def generate_tax_invoice_pdf(self, transaction_id: str, date_str: str, breakdown: Dict[str, Any]) -> Optional[io.BytesIO]:
        """
        Task 5.4: Tax Invoice generator (PDF) for the user.
        Uses ReportLab to generate a clean, compliant invoice.
        """
        try:
            from reportlab.pdfgen import canvas
            from reportlab.lib.pagesizes import A4
            
            buffer = io.BytesIO()
            p = canvas.Canvas(buffer, pagesize=A4)
            width, height = A4
            
            # Header
            p.setFont("Helvetica-Bold", 20)
            p.drawString(50, height - 50, "RouteMaster V2 - Tax Invoice")
            
            # Details
            p.setFont("Helvetica", 12)
            p.drawString(50, height - 100, f"Transaction ID: {transaction_id}")
            p.drawString(50, height - 120, f"Date: {date_str}")
            p.drawString(50, height - 140, "Merchant: RouteMaster Tech Pvt Ltd")
            p.drawString(50, height - 160, "GSTIN: 29AABCU9603R1ZX (Demo)")
            
            # Line Items
            p.line(50, height - 180, width - 50, height - 180)
            p.drawString(50, height - 210, "Base Fare:")
            p.drawString(400, height - 210, f"Rs. {breakdown['base_fare']:.2f}")
            
            p.drawString(50, height - 230, "Platform Fee:")
            p.drawString(400, height - 230, f"Rs. {breakdown['platform_fee']:.2f}")
            
            p.drawString(50, height - 250, f"GST ({breakdown['gst_rate']}):")
            p.drawString(400, height - 250, f"Rs. {breakdown['gst']:.2f}")
            
            p.drawString(50, height - 270, "Round Off:")
            p.drawString(400, height - 270, f"Rs. {breakdown['round_off']:.2f}")
            
            p.line(50, height - 290, width - 50, height - 290)
            p.setFont("Helvetica-Bold", 14)
            p.drawString(50, height - 320, "Total Amount:")
            p.drawString(400, height - 320, f"Rs. {breakdown['total']:.2f}")
            
            p.showPage()
            p.save()
            
            buffer.seek(0)
            return buffer
        except ImportError:
            logger.error("ReportLab not installed. Cannot generate PDF.")
            return None

    def export_gstr1_csv(self, db: Session, month: int, year: int) -> str:
        """
        Task 5.5: Monthly GSTR-1 export utility.
        Scans payments for the given month and extracts GST collected.
        Returns CSV string.
        """
        from database.models import Payment as PaymentModel
        
        # For demo, we just simulate extracting all completed payments
        # In a real system, we'd query by date range
        start_date = datetime(year, month, 1)
        if month == 12:
            end_date = datetime(year + 1, 1, 1)
        else:
            end_date = datetime(year, month + 1, 1)
            
        payments = db.query(PaymentModel).filter(
            PaymentModel.status == "completed",
            PaymentModel.created_at >= start_date,
            PaymentModel.created_at < end_date
        ).all()
        
        output = io.StringIO()
        writer = csv.writer(output)
        writer.writerow(["Invoice Date", "Order ID", "Total Amount", "Platform Fee", "GST Collected (18%)"])
        
        for p in payments:
            # We estimate backwards if we didn't store the exact breakdown in columns
            # In production, this would read from a dedicated ledger table
            amount = float(p.amount or 0)
            breakdown = self.calculate_breakdown(amount - 20.0) # Rough estimate for demo export
            writer.writerow([
                p.created_at.strftime("%Y-%m-%d"),
                p.razorpay_order_id,
                p.amount,
                breakdown["platform_fee"],
                breakdown["gst"]
            ])
            
        return output.getvalue()

    def simulate_settlement(self, transaction_date: datetime, is_holiday: bool = False) -> Dict[str, Any]:
        """
        Task 5.10: Merchant settlement delay simulator.
        Calculates when the merchant will actually receive the funds (T+1 or T+2).
        """
        delay_days = 2 if is_holiday else 1
        settlement_date = transaction_date + timedelta(days=delay_days)
        
        # Skip weekends
        while settlement_date.weekday() > 4: # 5 = Saturday, 6 = Sunday
            settlement_date += timedelta(days=1)
            
        return {
            "transaction_date": transaction_date.isoformat(),
            "expected_settlement_date": settlement_date.isoformat(),
            "settlement_type": f"T+{delay_days}",
            "status": "SETTLED" if datetime.utcnow() >= settlement_date else "PENDING"
        }

tax_engine = TaxEngineService()
