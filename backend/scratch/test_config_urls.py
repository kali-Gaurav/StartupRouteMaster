
import os
from database.config import Config

print(f"DATABASE_URL: {os.getenv('DATABASE_URL')}")
print(f"Transit Sync: {Config.GET_SQLALCHEMY_URL('transit', is_async=False)}")
print(f"Transit Async: {Config.GET_SQLALCHEMY_URL('transit', is_async=True)}")
print(f"User Sync: {Config.GET_SQLALCHEMY_URL('user', is_async=False)}")
