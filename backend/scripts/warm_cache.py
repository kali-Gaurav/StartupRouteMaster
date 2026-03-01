import requests
import time
import logging
from datetime import datetime, timedelta

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:8000/api/v2"
MAJOR_ROUTES = [
    ("NDLS", "BCT"),  # Delhi to Mumbai
    ("NDLS", "HWH"),  # Delhi to Kolkata
    ("BCT", "SBC"),   # Mumbai to Bangalore
    ("MAS", "NDLS"),  # Chennai to Delhi
    ("SBC", "NDLS"),  # Bangalore to Delhi
]

def warm_cache():
    logger.info("🚀 Starting Cache Warming (Ghost Searches)...")
    search_date = (datetime.now() + timedelta(days=2)).strftime("%Y-%m-%d")
    
    for src, dst in MAJOR_ROUTES:
        try:
            start = time.time()
            resp = requests.post(f"{BASE_URL}/search/unified", json={
                "source": src,
                "destination": dst,
                "date": search_date
            }, timeout=60)
            elapsed = time.time() - start
            logger.info(f"✅ Warmed {src} -> {dst} in {elapsed:.2f}s (Status: {resp.status_code})")
        except Exception as e:
            logger.error(f"❌ Failed to warm {src} -> {dst}: {e}")

if __name__ == "__main__":
    warm_cache()
