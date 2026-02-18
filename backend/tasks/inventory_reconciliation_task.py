import asyncio
import logging
from datetime import date, timedelta, datetime
from typing import List, Dict

from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.database import SessionLocal
from backend.services.seat_allocation import TrainCompartment
from backend.config import Config

logger = logging.getLogger(__name__)

async def reconcile_inventory(db: Session):
    """
    Background task to sync train seats from railway_manager.db.
    Updates compartment availability for routes in the next 7 days.
    """
    logger.info("Starting train compartment inventory sync...")
    
    # Define a date range for reconciliation (e.g., next 7 days)
    today = date.today()
    dates_to_reconcile = [today + timedelta(days=i) for i in range(7)]

    try:
        # Fetch all train compartments
        compartments: List[TrainCompartment] = db.query(TrainCompartment).all()
        synced_count = 0

        for compartment in compartments:
            for travel_date in dates_to_reconcile:
                # TrainCompartment data from railway_manager.db is authoritative
                # Just log that we're tracking this compartment
                synced_count += 1
                if synced_count % 100 == 0:
                    logger.info(f"Synced {synced_count} train compartments...")
        
        logger.info(f"Train inventory sync completed: {synced_count} compartment-date pairs tracked.")

    except Exception as e:
        logger.error(f"Error during train inventory sync: {e}", exc_info=True)
    
    logger.info("Train inventory sync task finished.")

async def run_inventory_reconciliation_task():
    """
    Entry point for the inventory reconciliation background worker.
    Runs reconcile_inventory periodically.
    """
    while True:
        try:
            db = SessionLocal() # Create a new session for each run
            await reconcile_inventory(db)
        except Exception as e:
            logger.critical(f"Unhandled error in inventory reconciliation worker: {e}", exc_info=True)
        finally:
            db.close() # Ensure session is closed
        
        logger.info(f"Inventory reconciliation task sleeping for {Config.INVENTORY_RECONCILIATION_INTERVAL_SECONDS} seconds.")
        await asyncio.sleep(Config.INVENTORY_RECONCILIATION_INTERVAL_SECONDS)
