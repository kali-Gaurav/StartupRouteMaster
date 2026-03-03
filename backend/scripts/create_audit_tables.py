import sys
import os

# Ensure backend package is importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from database.session import engine, Base
from database.models import (
    StationHealthIndex, SnapshotDiffLog, StationRank, StationTrainHistory
)

def create_tables():
    print("Creating new audit tables...")
    try:
        # This will only create tables that don't exist
        Base.metadata.create_all(bind=engine)
        print("Success! Tables created or already exist.")
    except Exception as e:
        print(f"Failed to create tables: {e}")

if __name__ == "__main__":
    create_tables()
