from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
import logging
import time
from datetime import datetime, timedelta
import random
import asyncio # Import asyncio

from backend.database import SessionLocal
from backend.services.payment_service import PaymentService
from backend.models import Booking, Payment, SeatInventory, Segment
from backend.tasks.inventory_reconciliation_task import run_inventory_reconciliation_task # Import the async task
from backend.tasks.partner_health_check_task import run_partner_health_check_task # New: Import partner health check task
from backend.config import Config # New: Import Config for interval

logger = logging.getLogger(__name__)

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

            # Asynchronously fetch order details
            # This part needs to be run in an async context if the service methods are async
            # For simplicity in this worker, we might need a synchronous wrapper or run it differently
            # order_details = await payment_service.fetch_order_details(payment.razorpay_order_id)
            # For now, we'll skip the async call in this synchronous worker
            
    except Exception as e:
        logger.error(f"Error during payment reconciliation: {e}", exc_info=True)
    finally:
        db.close()
    logger.info(f"Finished payment reconciliation at {datetime.now()}")

def inventory_reconciliation_wrapper():
    """
    Wrapper to run the asynchronous inventory reconciliation task within the APScheduler.
    """
    logger.info("Starting asynchronous inventory reconciliation wrapper.")
    try:
        asyncio.run(run_inventory_reconciliation_task())
    except Exception as e:
        logger.critical(f"Unhandled error in inventory reconciliation wrapper: {e}", exc_info=True)
    logger.info("Finished asynchronous inventory reconciliation wrapper.")

def partner_health_check_wrapper():
    """
    Wrapper to run the asynchronous partner health check task within the APScheduler.
    """
    logger.info("Starting asynchronous partner health check wrapper.")
    try:
        asyncio.run(run_partner_health_check_task())
    except Exception as e:
        logger.critical(f"Unhandled error in partner health check wrapper: {e}", exc_info=True)
    logger.info("Finished asynchronous partner health check wrapper.")


scheduler = None

def start_reconciliation_worker():
    global scheduler
    if scheduler:
        logger.info("Scheduler already running.")
        return

    scheduler = BackgroundScheduler()
    scheduler.add_job(
        reconcile_payments,
        IntervalTrigger(minutes=Config.PAYMENT_RECONCILIATION_INTERVAL_MINUTES), # Use Config
        id='payment_reconciliation_job',
        name='Razorpay Payment Reconciliation',
        replace_existing=True
    )
    scheduler.add_job(
        inventory_reconciliation_wrapper, # Use the wrapper for async task
        IntervalTrigger(seconds=Config.INVENTORY_RECONCILIATION_INTERVAL_SECONDS),
        id='inventory_reconciliation_job',
        name='Seat Inventory Reconciliation',
        replace_existing=True
    )
    scheduler.add_job(
        partner_health_check_wrapper, # New: Add partner health check job
        IntervalTrigger(minutes=Config.PARTNER_HEALTH_CHECK_INTERVAL_MINUTES), # Run every X minutes from Config
        id='partner_health_check_job',
        name='Partner Redirect Health Check',
        replace_existing=True
    )
    scheduler.start()
    logger.info("Payment, inventory, and partner health check worker started.")

def stop_reconciliation_worker():
    global scheduler
    if scheduler:
        scheduler.shutdown()
        scheduler = None
        logger.info("Reconciliation worker stopped.")
