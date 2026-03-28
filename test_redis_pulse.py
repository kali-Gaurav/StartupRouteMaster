import sys
import os
from pathlib import Path

# Add backend to sys.path
backend_path = Path("backend").resolve()
sys.path.append(str(backend_path))

from core.redis import verify_redis_connection

if __name__ == "__main__":
    success = verify_redis_connection()
    if success:
        print("✅ Redis Pulse: HEARTBEAT STABLE.")
    else:
        print("❌ Redis Pulse: HEARTBEAT FAILED.")
