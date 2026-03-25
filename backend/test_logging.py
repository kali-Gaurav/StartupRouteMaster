import logging
import time
from utils.structured_logging import setup_logging

print("Setting up logging...")
setup_logging()
logger = logging.getLogger("test_blocking")

print("Attempting to log a message...")
start = time.time()
logger.info("This is a test message to see if it blocks.")
print(f"Log successful in {time.time() - start:.3f}s")
