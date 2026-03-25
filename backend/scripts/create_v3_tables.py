import logging
from sqlalchemy import create_engine
from database.config import Config
from database.models import UserBase

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("v3-migration")

def migrate_to_v3_sync():
    print("🛠 [V3 MIGRATION] Running Synchronous Schema Injection...")
    
    # Use sync URL
    url = Config.GET_SQLALCHEMY_URL("user", is_async=False)
    
    # [Task 2] SSL Require for Supabase
    if "postgresql" in url and "sslmode" not in url:
        sep = "&" if "?" in url else "?"
        url = f"{url}{sep}sslmode=require"
    
    try:
        engine = create_engine(url)
        print(f"📡 Connecting to User DB (Sync): {url.split('@')[-1]}")
        UserBase.metadata.create_all(engine)
        print("✅ V3 Sync Migration Successful. Architectural tables are now live.")
    except Exception as e:
        logger.error(f"🛑 Sync Migration Failed: {e}")

if __name__ == "__main__":
    migrate_to_v3_sync()
