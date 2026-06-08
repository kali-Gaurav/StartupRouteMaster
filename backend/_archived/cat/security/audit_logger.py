"""
Audit Logging for the Contextual Availability Transformer (CAT) system.
Provides secure logging of prediction requests and responses.
"""

import logging
import json
import hashlib
import hmac
import time
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, Any, List
from pathlib import Path
import threading

from ..config import settings

logger = logging.getLogger(__name__)


class AuditLogger:
    """
    Logs prediction requests and responses for audit purposes.
    
    Excludes sensitive information and implements log retention policies.
    """
    
    # Fields to exclude from logs (sensitive data)
    EXCLUDED_FIELDS = {
        "api_key", "password", "secret", "token", "credential", "key",
        "private", "secret_key", "access_token", "refresh_token"
    }
    
    # Maximum log file size in bytes (100MB)
    MAX_LOG_SIZE = 100 * 1024 * 1024
    
    # Maximum number of log files to retain
    MAX_LOG_FILES = 10
    
    def __init__(
        self,
        log_dir: Optional[str] = None,
        retention_days: int = 90,
        log_level: str = "INFO"
    ):
        """
        Initialize audit logger.
        
        Args:
            log_dir: Directory for log files
            retention_days: Days to retain logs
            log_level: Logging level
        """
        self.log_dir = Path(log_dir) if log_dir else Path("logs/audit")
        self.retention_days = retention_days
        self.log_level = log_level
        
        # Create log directory if it doesn't exist
        self.log_dir.mkdir(parents=True, exist_ok=True)
        
        # Set up logger
        self._logger = logging.getLogger("audit")
        self._logger.setLevel(getattr(logging, log_level.upper()))
        
        # File handler
        log_file = self.log_dir / "predictions.log"
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(getattr(logging, log_level.upper()))
        
        # Formatter
        formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s'
        )
        file_handler.setFormatter(formatter)
        
        # Add handler if not already added
        if not self._logger.handlers:
            self._logger.addHandler(file_handler)
        
        # Log rotation tracking
        self._log_file = log_file
        self._log_size = 0
        self._lock = threading.Lock()
        
        # Load current log size
        if log_file.exists():
            self._log_size = log_file.stat().st_size
    
    def log_prediction_request(
        self,
        location_id: str,
        prediction_time: datetime,
        context_hours: int,
        client_id: Optional[str] = None,
        request_id: Optional[str] = None
    ) -> None:
        """
        Log a prediction request.
        
        Args:
            location_id: Location ID
            prediction_time: Prediction time
            context_hours: Context hours
            client_id: Client identifier (optional)
            request_id: Request identifier (optional)
        """
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "prediction_request",
            "location_id": self._hash_if_sensitive(location_id),
            "prediction_time": prediction_time.isoformat(),
            "context_hours": context_hours,
            "client_id": self._hash_if_sensitive(client_id) if client_id else None,
            "request_id": request_id,
            "status": "received"
        }
        
        self._logger.info(json.dumps(log_entry))
    
    def log_prediction_response(
        self,
        location_id: str,
        prediction_time: datetime,
        probability: float,
        confidence_lower: float,
        confidence_upper: float,
        request_id: Optional[str] = None,
        processing_time_ms: Optional[float] = None
    ) -> None:
        """
        Log a prediction response.
        
        Args:
            location_id: Location ID
            prediction_time: Prediction time
            probability: Predicted probability
            confidence_lower: Lower confidence bound
            confidence_upper: Upper confidence bound
            request_id: Request identifier (optional)
            processing_time_ms: Processing time in milliseconds (optional)
        """
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "prediction_response",
            "location_id": self._hash_if_sensitive(location_id),
            "prediction_time": prediction_time.isoformat(),
            "probability": probability,
            "confidence_interval": [confidence_lower, confidence_upper],
            "request_id": request_id,
            "processing_time_ms": processing_time_ms,
            "status": "completed"
        }
        
        self._logger.info(json.dumps(log_entry))
    
    def log_prediction_error(
        self,
        location_id: str,
        prediction_time: datetime,
        error_type: str,
        error_message: str,
        request_id: Optional[str] = None
    ) -> None:
        """
        Log a prediction error.
        
        Args:
            location_id: Location ID
            prediction_time: Prediction time
            error_type: Type of error
            error_message: Error message (sanitized)
            request_id: Request identifier (optional)
        """
        # Sanitize error message
        sanitized_message = self._sanitize_error_message(error_message)
        
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "prediction_error",
            "location_id": self._hash_if_sensitive(location_id),
            "prediction_time": prediction_time.isoformat(),
            "error_type": error_type,
            "error_message": sanitized_message,
            "request_id": request_id,
            "status": "error"
        }
        
        self._logger.warning(json.dumps(log_entry))
    
    def log_authentication_event(
        self,
        client_id: str,
        success: bool,
        api_key_hash: Optional[str] = None,
        ip_address: Optional[str] = None
    ) -> None:
        """
        Log an authentication event.
        
        Args:
            client_id: Client identifier
            success: Whether authentication succeeded
            api_key_hash: Hash of API key (optional)
            ip_address: Client IP address (optional)
        """
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "authentication",
            "client_id": self._hash_if_sensitive(client_id),
            "success": success,
            "api_key_hash": api_key_hash,
            "ip_address": ip_address,
            "status": "success" if success else "failed"
        }
        
        if success:
            self._logger.info(json.dumps(log_entry))
        else:
            self._logger.warning(json.dumps(log_entry))
    
    def log_rate_limit_event(
        self,
        client_id: str,
        request_count: int,
        limit: int,
        ip_address: Optional[str] = None
    ) -> None:
        """
        Log a rate limiting event.
        
        Args:
            client_id: Client identifier
            request_count: Current request count
            limit: Rate limit
            ip_address: Client IP address (optional)
        """
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "event_type": "rate_limit",
            "client_id": self._hash_if_sensitive(client_id),
            "request_count": request_count,
            "limit": limit,
            "ip_address": ip_address,
            "status": "exceeded"
        }
        
        try:
            self._logger.warning(json.dumps(log_entry))
        except TypeError:
            # Fallback if log entry contains non-serializable objects
            self._logger.warning(
                f"Rate limit exceeded for client: {client_id}, "
                f"request_count: {request_count}, limit: {limit}"
            )
    
    def _hash_if_sensitive(self, value: Optional[str]) -> Optional[str]:
        """
        Hash a value if it might be sensitive.
        
        Args:
            value: Value to potentially hash
            
        Returns:
            Hashed value or original value
        """
        if value is None:
            return None
        
        # Check if value looks like a sensitive field
        value_lower = value.lower()
        for field in self.EXCLUDED_FIELDS:
            if field in value_lower:
                # Hash the value
                return hashlib.sha256(value.encode()).hexdigest()[:16]
        
        return value
    
    def _sanitize_error_message(self, message: str) -> str:
        """
        Sanitize error message to remove sensitive information.
        
        Args:
            message: Error message to sanitize
            
        Returns:
            Sanitized error message
        """
        if not message:
            return message
        
        # Remove potential sensitive information
        sanitized = message
        
        # Remove API keys
        if hasattr(settings, 'api_key') and settings.api_key:
            sanitized = sanitized.replace(settings.api_key, "***")
        
        # Remove common sensitive patterns
        import re
        sanitized = re.sub(r'api_key[=:]\s*\S+', 'api_key=***', sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r'password[=:]\s*\S+', 'password=***', sanitized, flags=re.IGNORECASE)
        sanitized = re.sub(r'secret[=:]\s*\S+', 'secret=***', sanitized, flags=re.IGNORECASE)
        
        return sanitized
    
    def rotate_logs(self) -> List[str]:
        """
        Rotate log files if they exceed size limit.
        
        Returns:
            List of rotated log files
        """
        rotated_files = []
        
        with self._lock:
            if self._log_file.exists():
                current_size = self._log_file.stat().st_size
                
                if current_size >= self.MAX_LOG_SIZE:
                    # Rotate the log file
                    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
                    rotated_name = f"predictions_{timestamp}.log"
                    rotated_path = self.log_dir / rotated_name
                    
                    # Move current log to rotated name
                    self._log_file.rename(rotated_path)
                    rotated_files.append(str(rotated_path))
                    
                    # Create new log file
                    self._log_file.touch()
                    self._log_size = 0
                    
                    logger.info(f"Rotated log file: {rotated_name}")
                    
                    # Clean up old logs
                    self._cleanup_old_logs()
        
        return rotated_files
    
    def _cleanup_old_logs(self) -> None:
        """Clean up log files older than retention period."""
        cutoff_date = datetime.utcnow() - timedelta(days=self.retention_days)
        
        for log_file in self.log_dir.glob("predictions_*.log"):
            try:
                # Extract timestamp from filename
                filename = log_file.stem  # Remove .log extension
                if "_" in filename:
                    timestamp_str = filename.split("_")[-1]
                    file_date = datetime.strptime(timestamp_str, "%Y%m%d_%H%M%S")
                    
                    if file_date < cutoff_date:
                        log_file.unlink()
                        logger.info(f"Deleted old log file: {log_file.name}")
            except Exception as e:
                logger.warning(f"Failed to delete old log file {log_file}: {e}")
    
    def get_log_stats(self) -> Dict[str, Any]:
        """
        Get log file statistics.
        
        Returns:
            Dictionary with log statistics
        """
        stats = {
            "log_dir": str(self.log_dir),
            "retention_days": self.retention_days,
            "log_files": [],
            "total_size_bytes": 0
        }
        
        for log_file in self.log_dir.glob("predictions*.log"):
            stats["log_files"].append({
                "name": log_file.name,
                "size_bytes": log_file.stat().st_size,
                "created": datetime.fromtimestamp(log_file.stat().st_ctime).isoformat()
            })
            stats["total_size_bytes"] += log_file.stat().st_size
        
        return stats


def create_audit_logger() -> AuditLogger:
    """
    Create an audit logger instance from environment settings.
    
    Returns:
        Configured AuditLogger instance
    """
    log_dir = os.environ.get("CAT_AUDIT_LOG_DIR")
    retention_days = int(os.environ.get("CAT_LOG_RETENTION_DAYS", 90))
    
    return AuditLogger(
        log_dir=log_dir,
        retention_days=retention_days,
        log_level="INFO"
    )
