from backend.database import Base, engine
from backend.database.models import * # Import all models to ensure Base.metadata sees them

print("Attempting to create all tables in the database...")
Base.metadata.create_all(bind=engine)
print("Tables creation attempt finished.")