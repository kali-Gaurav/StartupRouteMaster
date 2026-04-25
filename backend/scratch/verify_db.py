
import asyncio
import logging
import sys
from pathlib import Path

# Add backend to path
backend_root = Path(__file__).resolve().parent.parent
if str(backend_root) not in sys.path:
    sys.path.append(str(backend_root))

from database.session import initialize_database_pools, SessionUser, SessionTransit
from database.models import User, Stop, Route, TrainMaster, Booking

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("db_verify")

async def verify_db():
    try:
        # Initialize pools manually since we are outside the app context
        await initialize_database_pools()
        
        # Check Table Counts
        # Note: SessionUser and SessionTransit are Proxies, so calling them returns a Session
        with SessionUser() as session:
            user_count = session.query(User).count()
            booking_count = session.query(Booking).count()
            logger.info(f"📊 User Store: {user_count} users, {booking_count} bookings")
            
        with SessionTransit() as session:
            stop_count = session.query(Stop).count()
            route_count = session.query(Route).count()
            train_count = session.query(TrainMaster).count()
            logger.info(f"📊 Transit Store: {stop_count} stops, {route_count} routes, {train_count} trains")
            
    except Exception as e:
        logger.error(f"❌ Database Verification Failed: {e}", exc_info=True)

if __name__ == "__main__":
    asyncio.run(verify_db())
