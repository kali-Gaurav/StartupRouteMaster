import sys
import os
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).resolve().parent.parent
sys.path.append(str(backend_path))

import redis
from core.redis import URL, OPTS

def test_redis():
    print(f"Testing Redis at {URL[:20]}...")
    try:
        r = redis.from_url(URL, **OPTS)
        r.ping()
        print("✅ Redis connection successful!")
        return True
    except redis.exceptions.AuthenticationError:
        print("❌ Redis Authentication failed!")
        return False
    except Exception as e:
        print(f"❌ Redis connection error: {e}")
        return False

if __name__ == "__main__":
    test_redis()
