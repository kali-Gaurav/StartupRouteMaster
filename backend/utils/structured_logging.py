import logging
import sys
import os
import random
from datetime import datetime
from contextvars import ContextVar
from typing import Optional, Any
from database.config import Config

# ContextVar to hold the unique request ID for the current async task
request_id_var: ContextVar[Optional[str]] = ContextVar("request_id", default=None)

def get_request_id() -> str:
    """Helper to get the current request ID or 'N/A'."""
    return request_id_var.get() or "N/A"

class JsonFormatter(logging.Formatter):
    """
    Task 30: Optimized JSON Log Formatter.
    Uses orjson for high-speed serialization.
    Prunes redundant metadata to save disk I/O on VPS.
    """
    def format(self, record):
        import orjson
        log_record = {
            "t": datetime.utcnow().isoformat(),
            "l": record.levelname,
            "n": record.name,
            "m": record.getMessage(),
            "rid": get_request_id().split("|")[0],
            "trace": get_request_id().split("|")[-1],
            "pid": record.process,
            "tid": record.threadName
        }
        
        # Only add verbose info for WARNING/ERROR
        if record.levelno >= logging.WARNING:
            log_record.update({
                "mod": record.module,
                "func": record.funcName,
                "line": record.lineno
            })
            if record.exc_info:
                # [Task 13.4] Error Correlation: Structured exceptions
                log_record["exc_type"] = record.exc_info[0].__name__
                log_record["exc"] = self.formatException(record.exc_info).replace('\n', ' ')
                
        return orjson.dumps(log_record).decode('utf-8')

class SamplingFilter(logging.Filter):
    """
    Task 30: High-Frequency Event Sampling.
    Drops routine logs based on a configurable probability.
    """
    def __init__(self, name: str = "", sample_rate: float = 0.1):
        super().__init__(name)
        self.sample_rate = sample_rate

    def filter(self, record):
        # Always log warnings and errors
        if record.levelno >= logging.WARNING:
            return True
        # Sample standard info logs
        return random.random() < self.sample_rate

class RequestIDFilter(logging.Filter):
    def filter(self, record):
        record.rid = get_request_id()
        return True

class EmojiStripperFilter(logging.Filter):
    """
    Ensures log messages are encodable in non-UTF-8 terminals (Windows cp1252).
    Strips emojis and other non-standard Unicode.
    """
    def filter(self, record):
        if isinstance(record.msg, str):
            # Encode to ascii and ignore errors, then back to str
            record.msg = record.msg.encode('ascii', 'ignore').decode('ascii').strip()
        return True

class BufferedStreamHandler(logging.StreamHandler):
    """
    Task 39: High-Efficiency Buffered Logging.
    Batches logs in memory and flushes periodically or when full.
    Reduces syscall overhead on VPS.
    """
    def __init__(self, stream=None, buffer_size=20, flush_interval=5.0):
        super().__init__(stream)
        self.buffer = []
        self.buffer_size = buffer_size
        self.flush_interval = flush_interval
        self.last_flush = time.time()
        self.lock = threading.Lock()

    def emit(self, record):
        try:
            msg = self.format(record)
            with self.lock:
                self.buffer.append(msg + self.terminator)
                
            now = time.time()
            if len(self.buffer) >= self.buffer_size or (now - self.last_flush) >= self.flush_interval:
                self.flush()
        except Exception:
            self.handleError(record)

    def flush(self):
        with self.lock:
            if not self.buffer: return
            try:
                self.stream.write("".join(self.buffer))
                self.stream.flush()
                self.buffer = []
                self.last_flush = time.time()
            except Exception:
                pass

import threading
import time

def setup_logging():
    """Configures logging based on the environment."""
    root_logger = logging.getLogger()
    
    # Task 30: Adaptive log level
    log_level = getattr(logging, Config.LOG_LEVEL.upper(), logging.INFO)
    if Config.SLIM_MODE and (log_level == logging.DEBUG or not os.getenv("LOG_LEVEL")):
        log_level = logging.INFO # Force INFO in slim mode
        
    root_logger.setLevel(log_level)

    # Clear existing handlers
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Use standard StreamHandler for now to avoid buffering/locking hangs [Task 30 FIX]
    handler = logging.StreamHandler(sys.stdout)
    handler.addFilter(RequestIDFilter())
    handler.addFilter(EmojiStripperFilter())
    
    if Config.ENVIRONMENT == "production":
        # Add sampling filter to noisy loggers in production
        # root_logger.addFilter(SamplingFilter(sample_rate=0.2))
        handler.setFormatter(JsonFormatter())
    else:
        standard_formatter = logging.Formatter(
            '%(asctime)s [%(levelname)s] %(name)s [RID:%(rid)s]: %(message)s'
        )
        handler.setFormatter(standard_formatter)
        
    root_logger.addHandler(handler)
    
    # Silence noisy third-party logs
    for noisy in ["uvicorn.access", "sqlalchemy.engine", "aiosqlite", "httpx", "httpcore"]:
        logging.getLogger(noisy).setLevel(logging.WARNING)
