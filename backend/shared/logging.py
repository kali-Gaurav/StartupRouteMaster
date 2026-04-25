"""
Shared logging module for microservices
"""
import logging
import sys
from shared.config import config

def setup_logging(name: str = "microservice"):
    """Setup logging for microservices"""
    logger = logging.getLogger(name)
    
    if logger.handlers:
        return logger
    
    # Set log level
    log_level = getattr(logging, config.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(log_level)
    
    # Create console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)
    
    # Create formatter
    if config.ENVIRONMENT == "production":
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
    else:
        formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        )
    
    handler.setFormatter(formatter)
    logger.addHandler(handler)
    
    # Silence noisy libraries
    for noisy in ["uvicorn", "sqlalchemy", "httpx"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)
    
    return logger