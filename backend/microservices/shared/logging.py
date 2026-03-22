
import logging
import json
import sys
from datetime import datetime
from contextvars import ContextVar
from typing import Optional
from .config import Config

# ContextVar to hold the unique request ID for the current async task
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)

def get_request_id() -> str:
    """Helper to get the current request ID or 'N/A'."""
    val = request_id_var.get()
    return val if val else "N/A"

class JsonFormatter(logging.Formatter):
    """
    Task 15: Centralized Structured Logging.
    Formats log records as JSON for cloud log ingestion.
    """
    def format(self, record):
        try:
            import orjson
            dumps = orjson.dumps
        except ImportError:
            dumps = json.dumps

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
        
        # Determine if we need to decode bytes (for orjson)
        res = dumps(log_record)
        if isinstance(res, bytes):
            return res.decode('utf-8')
        return res

class RequestIDFilter(logging.Filter):
    def filter(self, record):
        record.rid = get_request_id()
        return True

def setup_logging(service_name: str = "microservice"):
    """Configures logging based on the environment."""
    root_logger = logging.getLogger()
    level_name = getattr(Config, "LOG_LEVEL", "INFO").upper()
    root_logger.setLevel(getattr(logging, level_name, logging.INFO))

    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Use UTF-8 for StreamHandler to prevent emoji-related crashes on Windows
    import io
    if sys.stdout and not isinstance(sys.stdout, io.TextIOWrapper):
         try:
            sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
         except: pass
         
    handler = logging.StreamHandler(sys.stdout)    
    
    # Add RID filter to handler
    handler.addFilter(RequestIDFilter())
    
    if Config.ENVIRONMENT == "production":
        # Use JSON formatter in production
        handler.setFormatter(JsonFormatter())
    else:
        # Use standard readable formatter in development
        standard_formatter = logging.Formatter(
            f'%(asctime)s [%(levelname)s] {service_name}:%(name)s [RID:%(rid)s]: %(message)s'
        )
        handler.setFormatter(standard_formatter)
        
    root_logger.addHandler(handler)
    
    # Silence some noisy libraries
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)
