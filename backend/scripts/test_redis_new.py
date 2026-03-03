import redis
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def test_redis_new_token():
    # The user provided a slightly different token in the prompt text: 'di' instead of 'ti'
    token_di = "AZiZAAIncDIwNDdiZTY2NTNiY2Q0NTIyOTZiMTQ1MzlmNDRmZTVhOXAyMzkwNjU"
    token_ti = "AZiZAAIncDIwNDtiZTY2NTNiY2Q0NTIyOTZiMTQ1MzlmNDRmZTVhOXAyMzkwNjU"
    
    host = "amazed-rat-39065.upstash.io"
    port = 6379
    
    for label, token in [("DI-TOKEN", token_di), ("TI-TOKEN", token_ti)]:
        logger.info(f"Testing {label}...")
        try:
            r = redis.Redis(host=host, port=port, username="default", password=token, ssl=True, ssl_cert_reqs=None, decode_responses=True)
            if r.ping():
                logger.info(f"✅ SUCCESS with {label}!")
                return True
        except Exception as e:
            logger.error(f"❌ FAILED with {label}: {e}")
    return False

if __name__ == "__main__":
    test_redis_new_token()
