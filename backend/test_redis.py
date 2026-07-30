import os
import redis
from dotenv import load_dotenv

load_dotenv()

redis_url = os.getenv("REDIS_URL")
print(f"Testing Redis connection to: {redis_url}")

try:
    if redis_url.startswith("rediss://"):
        # Upstash rediss:// URL handling
        r = redis.from_url(redis_url, ssl_cert_reqs=None)
    else:
        r = redis.from_url(redis_url)
    
    r.ping()
    print("SUCCESS: Redis connection successful!")
except Exception as e:
    print(f"FAILURE: Redis connection failed: {e}")
