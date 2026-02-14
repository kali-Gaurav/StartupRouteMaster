from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import logging
import time
from datetime import datetime, timedelta

from backend.database import SessionLocal
from backend.services.payment_service import PaymentService
from backend.models import Booking, Payment

logger = logging.getLogger(__name__)

# This will be replaced with a more robust interval from config or env
RECONCILIATION_INTERVAL_MINUTES = 15

def reconcile_payments():
    """
    Worker task to reconcile pending payments with Razorpay.
    """
    logger.info(f"Starting payment reconciliation at {datetime.now()}")
    db = SessionLocal()
    try:
        payment_service = PaymentService()
        if not payment_service.is_configured():
            logger.warning("Payment service not configured, skipping reconciliation.")
            return

        # Fetch pending payments older than 10 minutes to avoid race conditions with webhooks
        time_threshold = datetime.utcnow() - timedelta(minutes=10)
        pending_payments = db.query(Payment).filter(
            Payment.status == "pending",
            Payment.created_at < time_threshold
        ).all()

        if not pending_payments:
            logger.info("No pending payments found for reconciliation.")
            return

        for payment in pending_payments:
            if not payment.razorpay_order_id:
                logger.warning(f"Payment {payment.id} is pending but has no razorpay_order_id. Cannot reconcile.")
                continue

            logger.info(f"Reconciling payment {payment.id} for Razorpay order {payment.razorpay_order_id}")

            order_details = payment_service.fetch_order_details(payment.razorpay_order_id)

            if not order_details:
                logger.warning(f"Could not fetch details for Razorpay order {payment.razorpay_order_id}.")
                continue

            if order_details.get("status") == "paid":
                payments_for_order = payment_service.fetch_payments_for_order(payment.razorpay_order_id)
                if not payments_for_order or not payments_for_order.get("items"):
                    logger.warning(f"Order {payment.razorpay_order_id} is 'paid' but no payments found.")
                    continue

                # Find a successful payment
                successful_payment = next((p for p in payments_for_order["items"] if p.get("status") == "captured"), None)

                if successful_payment:
                    logger.info(f"Razorpay order {payment.razorpay_order_id} is 'paid'. Marking internal payment as completed.")
                    payment.status = "completed"
                    payment.razorpay_payment_id = successful_payment.get("id")
                    db.add(payment)

                    if payment.booking_id:
                        booking = db.query(Booking).filter(Booking.id == payment.booking_id).first()
                        if booking and booking.status == "pending":
                            booking.status = "confirmed"
                            db.add(booking)
                            logger.info(f"Booking {booking.id} confirmed.")
                    
                    db.commit()
                    logger.info(f"Reconciliation successful for payment {payment.id}.")
                else:
                    logger.warning(f"Order {payment.razorpay_order_id} is 'paid' but no 'captured' payment found.")

            elif order_details.get("status") in ["created", "attempted"]:
                # If the order is still pending after a long time, we might want to mark it as failed.
                if datetime.utcnow() - payment.created_at > timedelta(hours=1):
                    logger.warning(f"Order {payment.razorpay_order_id} is still '{order_details.get('status')}' after 1 hour. Marking as failed.")
                    payment.status = "failed"
                    db.add(payment)
                    if payment.booking_id:
                        booking = db.query(Booking).filter(Booking.id == payment.booking_id).first()
                        if booking and booking.status == "pending":
                            booking.status = "failed"
                            db.add(booking)
                    db.commit()
            else: # e.g., expired, cancelled
                logger.warning(f"Order {payment.razorpay_order_id} has status '{order_details.get('status')}'. Marking payment as failed.")
                payment.status = "failed"
                db.add(payment)
                if payment.booking_id:
                    booking = db.query(Booking).filter(Booking.id == payment.booking_id).first()
                    if booking and booking.status == "pending":
                        booking.status = "failed"
                        db.add(booking)
                db.commit()

    except Exception as e:
        logger.error(f"Error during payment reconciliation: {e}", exc_info=True)
    finally:
        db.close()
    logger.info(f"Finished payment reconciliation at {datetime.now()}")


scheduler = None

def start_reconciliation_worker():
    global scheduler
    if scheduler:
        logger.info("Scheduler already running.")
        return

    scheduler = BackgroundScheduler()
    # Schedule reconcile_payments to run every RECONCILIATION_INTERVAL_MINUTES
    scheduler.add_job(
        reconcile_payments,
        IntervalTrigger(minutes=RECONCILIATION_INTERVAL_MINUTES),
        id='payment_reconciliation_job',
        name='Razorpay Payment Reconciliation',
        replace_existing=True
    )
    scheduler.start()
    logger.info("Payment reconciliation worker started.")

def stop_reconciliation_worker():
    global scheduler
    if scheduler:
        scheduler.shutdown()
        scheduler = None
        logger.info("Payment reconciliation worker stopped.")
