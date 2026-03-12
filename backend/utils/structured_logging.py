import logging
import json
import sys
from datetime import datetime
from contextvars import ContextVar
from typing import Optional
from database.config import Config

# ContextVar to hold the unique request ID for the current async task
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)

def get_request_id() -> str:
    """Helper to get the current request ID or 'N/A'."""
    return request_id_var.get() or "N/A"

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
            "rid": get_request_id(),
            "module": record.module,
            "func": record.funcName,
            "line": record.lineno,
            "env": Config.ENVIRONMENT
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        return orjson.dumps(log_record).decode('utf-8')

class RequestIDFilter(logging.Filter):
    def filter(self, record):
        record.rid = get_request_id()
        return True

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
    
    # Add RID filter to handler
    handler.addFilter(RequestIDFilter())
    
    if Config.ENVIRONMENT == "production":
        # Use JSON formatter in production
        handler.setFormatter(JsonFormatter())
    else:
        # Use standard readable formatter in development
        standard_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s [RID:%(rid)s]: %(message)s'
        )
        handler.setFormatter(standard_formatter)
        
    root_logger.addHandler(handler)
    
    # Silence some noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
