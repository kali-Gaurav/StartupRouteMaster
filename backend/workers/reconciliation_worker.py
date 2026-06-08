import asyncio
import logging
import time
from datetime import datetime, date, timedelta
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
from sqlalchemy import desc, or_

from database import get_db
from database.models import Payment as PaymentModel, Refund as RefundModel, User
from services.payment_service import PaymentService
from services.booking_service import BookingService
from services.telegram.bot import telegram_dispatcher
from services.telegram_session_manager import session_manager
from services.unified_travel_planner import UnifiedTravelPlanner, TravelRequest, TravelPreference
from utils.nlp_router import get_local_intent
from database.config import Config

logger = logging.getLogger("routemaster.reconciliation_worker")

class ReconciliationService:
    def __init__(self, db):
        self.db = db
        # PaymentService needs to be initialized with DB for some methods, like get_payment_details
        self.payment_service = PaymentService(db=db) 

    async def reconcile_razorpay_transactions(self):
        """
        [Daily Job] Reconcile Razorpay transactions with internal records.
        Fetches recent payments from Razorpay and updates internal status if needed.
        """
        logger.info("Starting Razorpay transaction reconciliation...")
        
        # 1. Fetch recent pending/unverified payments from our DB that have a Razorpay ID
        payments_to_check = self.db.query(PaymentModel).filter(
            or_(PaymentModel.status.in_(['pending', 'processing']), PaymentModel.status == 'pending'), # Explicitly check for pending/processing
            PaymentModel.razorpay_payment_id.isnot(None)
        ).order_by(desc(PaymentModel.created_at)).limit(100).all()

        if not payments_to_check:
            logger.info("No pending or processing Razorpay payments found to reconcile.")
            return

        logger.info(f"Found {len(payments_to_check)} pending/processing Razorpay payments to check.")

        for payment in payments_to_check:
            try:
                # Fetch payment status from Razorpay API
                razorpay_payment_details = await self.payment_service.get_payment_details(payment.razorpay_payment_id)
                
                if razorpay_payment_details and razorpay_payment_details.get("status"):
                    new_status = razorpay_payment_details["status"].upper()
                    
                    # Update internal status if it's different and indicates completion or failure
                    if new_status == "CAPTURED" and payment.status == "pending":
                        payment.status = "completed"
                        logger.info(f"✅ Payment {payment.id} (Razorpay: {payment.razorpay_payment_id}) status updated to COMPLETED.")
                        if payment.booking_id:
                            # Trigger booking confirmation if it's a booking payment
                            booking_service = BookingService(self.db)
                            booking_service.confirm_booking(payment.booking_id)
                    elif new_status in ("FAILED", "CANCELLED") and payment.status != "failed":
                        payment.status = "failed"
                        logger.error(f"⚠️ Payment {payment.id} (Razorpay: {payment.razorpay_payment_id}) status updated to FAILED.")
                        # Potentially trigger refund or cancellation logic here if needed
                else:
                    logger.warning(f"No status found for Razorpay payment {payment.razorpay_payment_id} (Internal ID: {payment.id}).")
                
                self.db.commit()
                self.db.refresh(payment)

            except Exception as e:
                logger.error(f"Error reconciling payment {payment.id} (Razorpay: {payment.razorpay_payment_id}): {e}", exc_info=True)
                self.db.rollback() # Rollback changes for this payment if an error occurs
        
        logger.info("Razorpay transaction reconciliation finished.")

    async def reconcile_refunds(self):
        """
        [Daily Job] Reconcile Razorpay refunds with internal records.
        Fetches refund statuses from Razorpay and updates internal RefundModel.
        """
        logger.info("Starting Razorpay refund reconciliation...")
        
        refunds_to_check = self.db.query(RefundModel).filter(
            RefundModel.status.in_(['PENDING', 'PROCESSING']) # Check for statuses needing update
        ).order_by(desc(RefundModel.created_at)).limit(50).all()

        if not refunds_to_check:
            logger.info("No pending or processing refunds found to reconcile.")
            return

        logger.info(f"Found {len(refunds_to_check)} pending/processing refunds to check.")

        for refund in refunds_to_check:
            if refund.razorpay_refund_id:
                try:
                    # Fetch refund status from Razorpay API
                    razorpay_refund_details = await self.payment_service.get_refund_details(refund.razorpay_refund_id)
                    
                    if razorpay_refund_details and razorpay_refund_details.get("status"):
                        new_status = razorpay_refund_details["status"].upper()
                        
                        if new_status in ("PROCESSED", "COMPLETED", "PAID") and refund.status != "COMPLETED":
                            refund.status = "COMPLETED"
                            refund.processed_at = datetime.utcnow()
                            logger.info(f"✅ Refund {refund.id} (Razorpay: {refund.razorpay_refund_id}) status updated to COMPLETED.")
                            # Update associated payment status if needed
                            if refund.payment_id:
                                payment = self.db.query(PaymentModel).filter(PaymentModel.id == refund.payment_id).first()
                                if payment:
                                    payment.refund_status = "COMPLETED"
                        elif new_status in ("FAILED", "CANCELLED") and refund.status != "FAILED":
                            refund.status = "FAILED"
                            logger.warning(f"⚠️ Refund {refund.id} (Razorpay: {refund.razorpay_refund_id}) status updated to FAILED.")
                        
                        self.db.commit()
                        self.db.refresh(refund)
                except Exception as e:
                    logger.error(f"Error reconciling refund {refund.id} (Razorpay: {refund.razorpay_refund_id}): {e}", exc_info=True)
                    self.db.rollback() # Rollback changes for this refund if an error occurs
            else:
                logger.warning(f"No Razorpay refund ID found for internal refund {refund.id}.")
        
        logger.info("Razorpay refund reconciliation finished.")


async def run_daily_reconciliations():
    """Runs all daily reconciliation jobs."""
    # Create a session for these jobs
    db = next(get_db()) # Get a DB session using __next__ as get_db is a generator
    try:
        service = ReconciliationService(db)
        await service.reconcile_razorpay_transactions()
        await service.reconcile_refunds()
    except Exception as e:
        logger.critical(f"Global reconciliation job failed: {e}", exc_info=True)
    finally:
        db.close()

if __name__ == "__main__":
    # Example of how to run this as a script (for testing or manual run)
    # In production, this would be scheduled via a cron job or task scheduler.
    print("Running manual reconciliation job...")
    asyncio.run(run_daily_reconciliations())
    print("Reconciliation job finished.")
