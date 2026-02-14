import asyncio
import logging
from datetime import date, timedelta, datetime
from typing import List, Dict

from sqlalchemy.orm import Session
from sqlalchemy import func

from backend.database import SessionLocal # Assuming SessionLocal is available for task workers
from backend.models import SeatInventory, Segment
from backend.services.external_api_service import fetch_external_inventory
from backend.config import Config

logger = logging.getLogger(__name__)

async def reconcile_inventory(db: Session):
    """
    Background task to sync internal seat counts with external partner data.
    """
    logger.info("Starting inventory reconciliation task...")
    
    # Define a date range for reconciliation (e.g., next 7 days)
    today = date.today()
    dates_to_reconcile = [today + timedelta(days=i) for i in range(7)]

    # Fetch all segments that could have inventory
    segments: List[Segment] = db.query(Segment).all()

    for segment in segments:
        for travel_date in dates_to_reconcile:
            travel_date_str = travel_date.isoformat()
            
            try:
                # 1. Fetch external inventory
                external_seats = await fetch_external_inventory(
                    segment_id=segment.id,
                    travel_date=travel_date_str
                )
                
                if external_seats is None:
                    logger.warning(f"Could not fetch external inventory for segment {segment.id} on {travel_date_str}. Skipping.")
                    continue

                # 2. Fetch or create internal inventory record
                inventory = db.query(SeatInventory).filter(
                    SeatInventory.segment_id == segment.id,
                    SeatInventory.travel_date == travel_date
                ).first()

                if inventory:
                    if inventory.seats_available != external_seats:
                        logger.info(
                            f"Reconciling inventory for segment {segment.id} on {travel_date_str}: "
                            f"Internal={inventory.seats_available}, External={external_seats}"
                        )
                        inventory.seats_available = external_seats
                        inventory.last_reconciled_at = datetime.utcnow()
                else:
                    logger.info(
                        f"Creating new inventory record for segment {segment.id} on {travel_date_str} "
                        f"with {external_seats} seats."
                    )
                    inventory = SeatInventory(
                        segment_id=segment.id,
                        travel_date=travel_date,
                        seats_available=external_seats,
                        last_reconciled_at=datetime.utcnow()
                    )
                    db.add(inventory)
                
                db.commit() # Commit each change or batch them
                db.refresh(inventory)

            except Exception as e:
                db.rollback()
                logger.error(
                    f"Error during inventory reconciliation for segment {segment.id} on {travel_date_str}: {e}",
                    exc_info=True
                )
    
    logger.info("Inventory reconciliation task finished.")

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
