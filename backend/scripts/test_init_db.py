import os, sys, asyncio
sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))
from database.config import Config
from database.session import engine_write
from database import init_db

# simulate unreachable host
Config.DATABASE_URL = "postgresql://user:pass@nonexistent.local:5432/db"
Config.OFFLINE_MODE = False

print("engine_write before", engine_write)
try:
    asyncio.run(init_db())
except Exception as e:
    print("init_db raised", e)

print("engine_write after", engine_write)
