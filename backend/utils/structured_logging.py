import logging
import json
import sys
from datetime import datetime
from database.config import Config

class JsonFormatter(logging.Formatter):
    """
    Task 15: Centralized Structured Logging.
    Formats log records as JSON for cloud log ingestion.
    [2.16] Uses orjson for non-ASCII safety.
    """
    def format(self, record):
        import orjson
        log_record = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "func": record.funcName,
            "line": record.lineno,
            "env": Config.ENVIRONMENT
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        return orjson.dumps(log_record).decode('utf-8')

def setup_logging():
    """Configures logging based on the environment."""
    root_logger = logging.getLogger()
    root_logger.setLevel(getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO))

    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Use UTF-8 for StreamHandler to prevent emoji-related crashes on Windows
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    handler = logging.StreamHandler(sys.stdout)    
    if Config.ENVIRONMENT == "production":
        # Use JSON formatter in production
        handler.setFormatter(JsonFormatter())
    else:
        # Use standard readable formatter in development
        standard_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s: %(message)s'
        )
        handler.setFormatter(standard_formatter)
        
    root_logger.addHandler(handler)
    
    # Silence some noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
