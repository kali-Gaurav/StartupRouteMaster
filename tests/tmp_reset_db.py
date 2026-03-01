from backend.database import engine, Base
from backend.database.models import Stop, Trip, Route, Agency, Calendar, StopTime, User
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def reset_db():
    logger.info("Dropping all tables...")
    Base.metadata.drop_all(bind=engine)
    logger.info("Creating all tables...")
    Base.metadata.create_all(bind=engine)
    logger.info("Database reset successfully.")

if __name__ == "__main__":
    reset_db()
