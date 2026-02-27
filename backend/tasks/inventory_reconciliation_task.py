import asyncio
import logging
from datetime import date, timedelta, datetime
from typing import List, Dict

from sqlalchemy.orm import Session
from sqlalchemy import func

from database.session import SessionLocal
from database.models import SeatInventory, Coach, Trip
from database.config import Config

logger = logging.getLogger(__name__)

async def reconcile_inventory(db: Session):
    """
    Background task to sync train seats from database configuration.
    Ensures SeatInventory exists for upcoming journeys.
    """
    logger.info("Starting production inventory reconciliation...")
    
    today = date.today()
    dates_to_reconcile = [today + timedelta(days=i) for i in range(7)]

    try:
        # Fetch all trips with their coach configurations
        trips = db.query(Trip).all()
        synced_count = 0

        for trip in trips:
            coaches = db.query(Coach).filter(Coach.trip_id == trip.id).all()
            for travel_date in dates_to_reconcile:
                for coach in coaches:
                    # Check if SeatInventory entry exists for this trip, date, and coach type
                    # Using simplified stop_time_id mapping for now
                    existing = db.query(SeatInventory).filter(
                        SeatInventory.stop_time_id == trip.id,
                        SeatInventory.travel_date == travel_date,
                        SeatInventory.coach_type == coach.class_type
                    ).first()
                    
                    if not existing:
                        new_inv = SeatInventory(
                            stop_time_id=trip.id,
                            travel_date=travel_date,
                            coach_type=coach.class_type,
                            seats_available=coach.total_seats,
                            total_seats=coach.total_seats
                        )
                        db.add(new_inv)
                        synced_count += 1
                
        db.commit()
        logger.info(f"Production inventory reconciliation completed: {synced_count} new inventory records created.")

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
