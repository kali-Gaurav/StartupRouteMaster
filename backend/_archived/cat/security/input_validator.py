"""
Input Validation for the Contextual Availability Transformer (CAT) system.
Provides validation utilities to prevent injection attacks and ensure data integrity.
"""

import re
import logging
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from pydantic import ValidationError

from ..models.schemas import (
    PredictionRequest, BatchPredictionRequest, AvailabilityPrediction
)

logger = logging.getLogger(__name__)


class InputValidator:
    """
    Validates input parameters to prevent injection attacks and ensure data integrity.
    
    Implements schema validation, sanitization, and security checks.
    """
    
    # Maximum request size in bytes (10MB)
    MAX_REQUEST_SIZE = 10 * 1024 * 1024
    
    # Maximum prediction horizon in hours
    MAX_PREDICTION_HORIZON_HOURS = 168
    
    # Maximum batch size
    MAX_BATCH_SIZE = 100
    
    # SQL injection patterns
    SQL_INJECTION_PATTERNS = [
        r"(\bUNION\b.*\bSELECT\b)",
        r"(\bSELECT\b.*\bFROM\b)",
        r"(\bINSERT\b.*\bINTO\b)",
        r"(\bDELETE\b.*\bFROM\b)",
        r"(\bDROP\b.*\bTABLE\b)",
        r"(\bALTER\b.*\bTABLE\b)",
        r"(\bUPDATE\b.*\bSET\b)",
        r"(;.*\b--\b)",
        r"(\bOR\b.*=.*)",
        r"(\bAND\b.*=.*)",
    ]
    
    # XSS patterns
    XSS_PATTERNS = [
        r"<script[^>]*>",
        r"javascript:",
        r"on\w+\s*=",
        r"<iframe[^>]*>",
        r"<object[^>]*>",
        r"<embed[^>]*>",
    ]
    
    def __init__(
        self,
        max_request_size: int = None,
        max_prediction_horizon_hours: int = None,
        max_batch_size: int = None
    ):
        """
        Initialize input validator.
        
        Args:
            max_request_size: Maximum request size in bytes
            max_prediction_horizon_hours: Maximum prediction horizon in hours
            max_batch_size: Maximum batch size
        """
        self.max_request_size = max_request_size or self.MAX_REQUEST_SIZE
        self.max_prediction_horizon_hours = (
            max_prediction_horizon_hours or self.MAX_PREDICTION_HORIZON_HOURS
        )
        self.max_batch_size = max_batch_size or self.MAX_BATCH_SIZE
        
        # Compile regex patterns
        self._sql_patterns = [re.compile(p, re.IGNORECASE) for p in self.SQL_INJECTION_PATTERNS]
        self._xss_patterns = [re.compile(p, re.IGNORECASE) for p in self.XSS_PATTERNS]
    
    def validate_request_size(self, request_data: bytes) -> bool:
        """
        Validate request size.
        
        Args:
            request_data: Raw request data
            
        Returns:
            True if size is within limits
        """
        if len(request_data) > self.max_request_size:
            logger.warning(
                f"Request size {len(request_data)} exceeds limit {self.max_request_size}"
            )
            return False
        return True
    
    def validate_location_id(self, location_id: str) -> Tuple[bool, Optional[str]]:
        """
        Validate location ID format.
        
        Args:
            location_id: Location ID to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if not location_id or not location_id.strip():
            return False, "Location ID cannot be empty"
        
        # Check for injection patterns
        if self._contains_injection_patterns(location_id):
            return False, "Location ID contains invalid characters"
        
        # Check length
        if len(location_id) > 256:
            return False, "Location ID too long"
        
        # Allow alphanumeric, hyphens, underscores, and dots
        if not re.match(r'^[a-zA-Z0-9._-]+$', location_id):
            return False, "Location ID contains invalid characters"
        
        return True, None
    
    def validate_prediction_time(self, prediction_time: datetime) -> Tuple[bool, Optional[str]]:
        """
        Validate prediction time.
        
        Args:
            prediction_time: Prediction time to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        now = datetime.utcnow()
        
        # Check if prediction time is in the past
        if prediction_time < now:
            return False, "Prediction time cannot be in the past"
        
        # Check prediction horizon
        horizon = prediction_time - now
        if horizon.total_seconds() > self.max_prediction_horizon_hours * 3600:
            return False, f"Prediction time exceeds maximum horizon of {self.max_prediction_horizon_hours} hours"
        
        return True, None
    
    def validate_context_hours(self, context_hours: int) -> Tuple[bool, Optional[str]]:
        """
        Validate context hours.
        
        Args:
            context_hours: Context hours to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if context_hours < 1:
            return False, "Context hours must be at least 1"
        
        if context_hours > self.max_prediction_horizon_hours:
            return False, f"Context hours cannot exceed {self.max_prediction_horizon_hours}"
        
        return True, None
    
    def validate_batch_size(self, predictions: List) -> Tuple[bool, Optional[str]]:
        """
        Validate batch size.
        
        Args:
            predictions: List of prediction requests
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        if len(predictions) > self.max_batch_size:
            return False, f"Batch size exceeds maximum of {self.max_batch_size}"
        
        if len(predictions) < 1:
            return False, "Batch must contain at least one prediction"
        
        return True, None
    
    def validate_prediction_request(
        self,
        request: PredictionRequest
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate a prediction request.
        
        Args:
            request: PredictionRequest to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Validate location ID
        valid, error = self.validate_location_id(request.location_id)
        if not valid:
            return False, error
        
        # Validate prediction time
        valid, error = self.validate_prediction_time(request.prediction_time)
        if not valid:
            return False, error
        
        # Validate context hours
        valid, error = self.validate_context_hours(request.context_hours)
        if not valid:
            return False, error
        
        return True, None
    
    def validate_batch_request(
        self,
        request: BatchPredictionRequest
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate a batch prediction request.
        
        Args:
            request: BatchPredictionRequest to validate
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        # Validate batch size
        valid, error = self.validate_batch_size(request.predictions)
        if not valid:
            return False, error
        
        # Validate each prediction in the batch
        for i, pred_request in enumerate(request.predictions):
            valid, error = self.validate_prediction_request(pred_request)
            if not valid:
                return False, f"Prediction {i}: {error}"
        
        return True, None
    
    def _contains_injection_patterns(self, text: str) -> bool:
        """
        Check if text contains injection patterns.
        
        Args:
            text: Text to check
            
        Returns:
            True if injection patterns found
        """
        # Check SQL injection patterns
        for pattern in self._sql_patterns:
            if pattern.search(text):
                logger.warning(f"SQL injection pattern detected: {pattern.pattern}")
                return True
        
        # Check XSS patterns
        for pattern in self._xss_patterns:
            if pattern.search(text):
                logger.warning(f"XSS pattern detected: {pattern.pattern}")
                return True
        
        return False
    
    def sanitize_input(self, text: str) -> str:
        """
        Sanitize input text by removing potentially dangerous characters.
        
        Args:
            text: Text to sanitize
            
        Returns:
            Sanitized text
        """
        if not text:
            return text
        
        # Remove null bytes
        text = text.replace('\x00', '')
        
        # Remove control characters (except newlines and tabs)
        text = re.sub(r'[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]', '', text)
        
        return text.strip()
    
    def validate_schema(self, data: Dict[str, Any], schema_class) -> Tuple[bool, Optional[str]]:
        """
        Validate data against a Pydantic schema.
        
        Args:
            data: Data to validate
            schema_class: Pydantic schema class
            
        Returns:
            Tuple of (is_valid, error_message)
        """
        try:
            schema_class(**data)
            return True, None
        except ValidationError as e:
            error_msg = str(e)
            logger.warning(f"Schema validation error: {error_msg}")
            return False, error_msg


def validate_request(request: PredictionRequest) -> Tuple[bool, Optional[str]]:
    """
    Validate a prediction request using default validator.
    
    Args:
        request: PredictionRequest to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    validator = InputValidator()
    return validator.validate_prediction_request(request)


def validate_batch_request(request: BatchPredictionRequest) -> Tuple[bool, Optional[str]]:
    """
    Validate a batch prediction request using default validator.
    
    Args:
        request: BatchPredictionRequest to validate
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    validator = InputValidator()
    return validator.validate_batch_request(request)


def validate_prediction_request(
    location_id: str,
    prediction_time: datetime,
    context_hours: int = 24
) -> Tuple[bool, Optional[str]]:
    """
    Validate prediction request parameters.
    
    Args:
        location_id: Location ID
        prediction_time: Prediction time
        context_hours: Context hours
        
    Returns:
        Tuple of (is_valid, error_message)
    """
    validator = InputValidator()
    
    # Validate location ID
    valid, error = validator.validate_location_id(location_id)
    if not valid:
        return False, error
    
    # Validate prediction time
    valid, error = validator.validate_prediction_time(prediction_time)
    if not valid:
        return False, error
    
    # Validate context hours
    valid, error = validator.validate_context_hours(context_hours)
    if not valid:
        return False, error
    
    return True, None
