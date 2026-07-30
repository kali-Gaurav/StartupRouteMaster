import asyncio
import logging
from datetime import date, timedelta, datetime
from typing import List, Dict, Optional

from sqlalchemy.orm import Session
from sqlalchemy import text

from database.session import SessionLocal
from database.models import SeatInventory, Coach, Trip
from database.config import Config

logger = logging.getLogger(__name__)

async def reconcile_inventory(user_db: Session, transit_db: Session):
    """
    Background task to sync train seats from database configuration.
    Ensures SeatInventory exists for upcoming journeys.
    [Nexus Fix] Cross-Database Sync: Transit (SQLite) -> User (Postgres)
    """
    logger.info("Starting cross-database inventory reconciliation...")
    
    today = date.today()
    dates_to_reconcile = [today + timedelta(days=i) for i in range(7)]

    try:
        # 1. Fetch trip and coach data from Transit DB
        logger.info("Fetching source data from Transit DB...")
        source_data = transit_db.execute(text("""
            SELECT 
                t.train_no, 
                c.class_type, 
                c.total_seats,
                COALESCE(
                    (SELECT s.code FROM stop_times st JOIN stops s ON st.stop_id = s.id 
                     WHERE st.trip_id = t.id ORDER BY st.stop_sequence ASC LIMIT 1), 
                    'UNKNOWN'
                ) as source_station_code,
                COALESCE(
                    (SELECT s.code FROM stop_times st JOIN stops s ON st.stop_id = s.id 
                     WHERE st.trip_id = t.id ORDER BY st.stop_sequence DESC LIMIT 1), 
                    'UNKNOWN'
                ) as dest_station_code
            FROM trips t
            JOIN coaches c ON t.id = c.trip_id
            WHERE t.train_no IS NOT NULL AND t.train_no != ''
        """)).mappings().all()
        
        if not source_data:
            logger.warning("No trip/coach data found in Transit DB.")
            return

        # 2. Fetch existing inventory keys from User DB to avoid duplicates efficiently
        # Key format: (train_number, journey_date, class_type, quota)
        existing_keys = set()
        for travel_date in dates_to_reconcile:
            existing = user_db.query(
                SeatInventory.train_number, 
                SeatInventory.journey_date, 
                SeatInventory.class_type, 
                SeatInventory.quota
            ).filter(SeatInventory.journey_date == travel_date).all()
            for row in existing:
                existing_keys.add((row[0], row[1], row[2], row[3]))

        synced_count = 0
        new_records = []

        # 3. Reconcile
        for row in source_data:
            train_number = row["train_no"]
            class_type = row["class_type"]
            total_seats = row["total_seats"]
            
            for travel_date in dates_to_reconcile:
                key = (train_number, travel_date, class_type, "GENERAL")
                if key not in existing_keys:
                    new_inv = SeatInventory(
                        train_number=train_number,
                        from_station_code=row["source_station_code"],
                        to_station_code=row["dest_station_code"],
                        journey_date=travel_date,
                        class_type=class_type,
                        quota="GENERAL",
                        total_seats=total_seats,
                        available_seats=total_seats,
                        status_text=f"AVAILABLE {total_seats}"
                    )
                    new_records.append(new_inv)
                    synced_count += 1
                    
                    # Batch flush to avoid memory bloat
                    if len(new_records) >= 500:
                        user_db.add_all(new_records)
                        user_db.commit()
                        new_records = []

        if new_records:
            user_db.add_all(new_records)
            user_db.commit()
            
        logger.info(f"Cross-database inventory reconciliation completed: {synced_count} new inventory records created.")

    except Exception as e:
        logger.error(f"Error during train inventory sync: {e}", exc_info=True)
        user_db.rollback()
    
    logger.info("Train inventory sync task finished.")

async def run_inventory_reconciliation_task():
    """
    Entry point for the inventory reconciliation background worker.
    Runs reconcile_inventory periodically.
    """
    from database.session import SessionLocal, SessionTransit
    while True:
        user_db: Optional[Session] = None
        transit_db: Optional[Session] = None
        try:
            user_db = SessionLocal()
            transit_db = SessionTransit()
            await reconcile_inventory(user_db, transit_db)
        except Exception as e:
            logger.critical(f"Unhandled error in inventory reconciliation worker: {e}", exc_info=True)
        finally:
            if user_db: user_db.close()
            if transit_db: transit_db.close()
        
        logger.info(f"Inventory reconciliation task sleeping for {Config.INVENTORY_RECONCILIATION_INTERVAL_SECONDS} seconds.")
        await asyncio.sleep(Config.INVENTORY_RECONCILIATION_INTERVAL_SECONDS)
