
import os
import redis
from dotenv import load_dotenv

# Load .env
load_dotenv()

redis_url = os.getenv("REDIS_URL")

print(f"Testing Redis Connection to: {redis_url.split('@')[-1] if redis_url else 'NONE'}")

try:
    if not redis_url:
        print("❌ REDIS_URL not found in .env")
    else:
        # Upstash usually needs ssl=True for rediss://
        r = redis.from_url(redis_url, decode_responses=True, ssl_cert_reqs=None)
        r.ping()
        print("✅ Redis Connection Successful!")
        
        # Test basic operations
        r.set("test_key", "hello_redis")
        val = r.get("test_key")
        print(f"✅ Basic SET/GET Successful: {val}")
        
except redis.exceptions.AuthenticationError as e:
    print(f"❌ Redis Authentication Error: {e}")
except redis.exceptions.ConnectionError as e:
    print(f"❌ Redis Connection Error: {e}")
except Exception as e:
    print(f"❌ Redis Unexpected Error: {type(e).__name__}: {e}")
