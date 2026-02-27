import redis
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_redis_direct():
    token = "AZiZAAIncDIwNDtiZTY2NTNiY2Q0NTIyOTZiMTQ1MzlmNDRmZTVhOXAyMzkwNjU"
    host = "amazed-rat-39065.upstash.io"
    port = 6379
    
    logger.info("Testing with username 'default'...")
    try:
        r1 = redis.Redis(host=host, port=port, username="default", password=token, ssl=True, ssl_cert_reqs=None)
        r1.ping()
        logger.info("✅ SUCCESS with 'default'")
        return
    except Exception as e:
        logger.error(f"❌ FAILED with 'default': {e}")

    logger.info("Testing with no username...")
    try:
        r2 = redis.Redis(host=host, port=port, password=token, ssl=True, ssl_cert_reqs=None)
        r2.ping()
        logger.info("✅ SUCCESS with no username")
        return
    except Exception as e:
        logger.error(f"❌ FAILED with no username: {e}")

if __name__ == "__main__":
    test_redis_direct()
