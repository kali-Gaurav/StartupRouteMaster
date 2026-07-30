import os
from pathlib import Path
from dotenv import load_dotenv
import redis

# Load .env
env_path = Path(__file__).resolve().parent / '.env'
load_dotenv(dotenv_path=env_path)

redis_url = os.getenv("REDIS_URL")
print(f"Testing Redis URL: {redis_url[:20]}...{redis_url[-20:]}")

try:
    client = redis.from_url(redis_url, decode_responses=True, ssl_cert_reqs=None)
    pong = client.ping()
    print(f"Redis Ping: {pong}")
except Exception as e:
    print(f"Redis Error: {e}")
