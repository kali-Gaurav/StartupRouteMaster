
import os
import sys
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).resolve().parent.parent
sys.path.append(str(backend_path))

from sqlalchemy import create_engine, text
from database.config import Config
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("drop_tables")

def drop_tables():
    url = Config.DATABASE_URL
    if not url or Config.OFFLINE_MODE:
        logger.error("OFFLINE_MODE is enabled or DATABASE_URL is missing.")
        return

    try:
        engine = create_engine(url)
        with engine.connect() as conn:
            # We use a single string with all table names to drop
            tables = [
                "users", "profiles", "bookings", "passenger_details", "payments", 
                "stop_times", "trips", "gtfs_routes", "agency", "stops", 
                "calendar", "calendar_dates", "coaches", "seats", "fares", 
                "transfers", "subscriptions", "unlocked_routes", "disruptions", 
                "seat_inventory", "commission_tracking", "reviews", "webhook_events", 
                "realtime_data", "rl_feedback_logs", "route_shapes", "frequencies", 
                "station_facilities", "cancellation_rules", "waiting_list", 
                "booking_requests", "booking_request_passengers", "booking_queue", 
                "booking_results", "refunds", "execution_logs", "precalculated_routes", 
                "vehicles", "stations", "station_departures_indexed", "time_index_keys", 
                "station_departures", "stop_departures", "stations_master", 
                "train_states", "seat_availability", "trains_master", 
                "train_stations", "train_live_updates", "train_live_updates_indexed"
            ]
            
            logger.info("Dropping all application tables CASCADE...")
            # Some environments might not support large DROP TABLE lists, so we can do it in a loop
            # but CASCADE is safer with a list.
            conn.execute(text(f"DROP TABLE IF EXISTS {', '.join(tables)} CASCADE;"))
            conn.commit()
            logger.info("✅ All application tables dropped successfully.")
    except Exception as e:
        logger.error(f"❌ Failed to drop tables: {e}")

if __name__ == "__main__":
    drop_tables()
