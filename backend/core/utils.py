"""
Shared Utility Functions - Cross-engine helpers

Consolidates utility functions used across multiple engines:
- Cache key generation (cache/manager.py)
- Occupancy calculations (inventory + cache)
- Error handling decorators
- Explanation generation (pricing)
"""

import hashlib
import logging
import time
import functools
from typing import Dict, Any, Callable, Optional
from datetime import date, datetime

logger = logging.getLogger(__name__)


# ==============================================================================
# CACHE KEY GENERATION UTILITIES
# ==============================================================================

class CacheKeyGenerator:
    """Generates consistent cache keys across the system."""

    # Standard prefixes for different cache types
    ROUTE_PREFIX = "route"
    AVAILABILITY_PREFIX = "availability"
    OCCUPANCY_PREFIX = "occupancy"
    ML_PREFIX = "ml"
    SCHEDULE_PREFIX = "schedule"

    @staticmethod
    def generate_key(*parts) -> str:
        """
        Generate a cache key from multiple parts.

        Args:
            *parts: Variable number of string/hashable parts

        Returns:
            Hashed cache key
        """
        key_data = ":".join(str(part) for part in parts)
        return hashlib.sha256(key_data.encode()).hexdigest()[:16]

    @staticmethod
    def route_query_key(from_station: str, to_station: str, date: date, **kwargs) -> str:
        """Generate cache key for route query."""
        parts = [
            CacheKeyGenerator.ROUTE_PREFIX,
            from_station,
            to_station,
            date.isoformat(),
        ]

        # Add optional parts
        if 'class_preference' in kwargs:
            parts.append(f"class_{kwargs['class_preference']}")
        if 'max_transfers' in kwargs:
            parts.append(f"transfers_{kwargs['max_transfers']}")

        return ":".join(parts) + ":" + CacheKeyGenerator.generate_key(*parts)

    @staticmethod
    def availability_key(train_id: int, from_stop: int, to_stop: int, date: date, quota: str) -> str:
        """Generate cache key for availability."""
        parts = [
            CacheKeyGenerator.AVAILABILITY_PREFIX,
            str(train_id),
            str(from_stop),
            str(to_stop),
            date.isoformat(),
            quota,
        ]
        return ":".join(parts) + ":" + CacheKeyGenerator.generate_key(*parts)

    @staticmethod
    def occupancy_key(train_id: int, date: date, segment_id: Optional[int] = None) -> str:
        """Generate cache key for occupancy data."""
        parts = [
            CacheKeyGenerator.OCCUPANCY_PREFIX,
            str(train_id),
            date.isoformat(),
        ]
        if segment_id:
            parts.append(f"segment_{segment_id}")

        return ":".join(parts) + ":" + CacheKeyGenerator.generate_key(*parts)

    @staticmethod
    def ml_features_key(model_id: str, context_id: str) -> str:
        """Generate cache key for ML features."""
        parts = [CacheKeyGenerator.ML_PREFIX, model_id, context_id]
        return ":".join(parts) + ":" + CacheKeyGenerator.generate_key(*parts)


# ==============================================================================
# OCCUPANCY & AVAILABILITY CALCULATION UTILITIES
# ==============================================================================

class OccupancyCalculator:
    """Consolidates occupancy and availability calculations."""

    @staticmethod
    def calculate_occupancy_rate(occupied: int, total: int) -> float:
        """
        Calculate occupancy rate.

        Args:
            occupied: Number of occupied seats/slots
            total: Total available seats/slots

        Returns:
            Occupancy rate (0.0 to 1.0)
        """
        if total <= 0:
            return 0.0
        rate = occupied / total
        return max(0.0, min(1.0, rate))  # Clamp to [0, 1]

    @staticmethod
    def calculate_available_count(total: int, occupied: int) -> int:
        """Calculate available count."""
        return max(0, total - occupied)

    @staticmethod
    def get_occupancy_level(occupancy_rate: float) -> str:
        """
        Get human-readable occupancy level.

        Args:
            occupancy_rate: Rate from 0.0 to 1.0

        Returns:
            Level name: 'Empty', 'Low', 'Moderate', 'High', 'Full'
        """
        if occupancy_rate < 0.2:
            return "Empty"
        elif occupancy_rate < 0.5:
            return "Low"
        elif occupancy_rate < 0.8:
            return "Moderate"
        elif occupancy_rate < 0.95:
            return "High"
        else:
            return "Full"

    @staticmethod
    def calculate_breakeven_price_multiplier(occupancy_rate: float) -> float:
        """
        Calculate suggested price multiplier based on occupancy.

        Used for dynamic pricing - higher occupancy -> higher prices.

        Args:
            occupancy_rate: Rate from 0.0 to 1.0

        Returns:
            Suggested price multiplier (0.8 to 1.8)
        """
        if occupancy_rate < 0.3:
            return 0.85  # Heavy discount
        elif occupancy_rate < 0.6:
            return 1.0   # Standard
        elif occupancy_rate < 0.8:
            return 1.2   # Premium
        else:
            return 1.5   # High demand


# ==============================================================================
# ERROR HANDLING DECORATORS
# ==============================================================================

def error_handler(default_return=None, log_level="error"):
    """
    Decorator for consistent error handling across engines.

    Args:
        default_return: Value to return if exception occurs
        log_level: Logging level ('debug', 'info', 'warning', 'error')

    Example:
        @error_handler(default_return=[], log_level='warning')
        def fetch_data():
            return some_api_call()
    """
    def decorator(func: Callable):
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                log_fn = getattr(logger, log_level, logger.error)
                log_fn(f"Error in {func.__name__}: {e}")
                return default_return

        # Add async variant
        if hasattr(func, '__await__'):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    log_fn = getattr(logger, log_level, logger.error)
                    log_fn(f"Error in {func.__name__}: {e}")
                    return default_return

            return async_wrapper

        return wrapper

    return decorator


def time_operation(operation_name: str = None):
    """
    Decorator to time function execution.

    Args:
        operation_name: Name for logging (defaults to function name)

    Example:
        @time_operation("database_fetch")
        def get_data():
            pass
    """
    def decorator(func: Callable):
        op_name = operation_name or func.__name__

        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            start = time.time()
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start) * 1000
                logger.debug(f"✓ {op_name}: {duration_ms:.1f}ms")
                return result
            except Exception as e:
                duration_ms = (time.time() - start) * 1000
                logger.error(f"✗ {op_name}: {duration_ms:.1f}ms - {e}")
                raise

        if hasattr(func, '__await__'):
            @functools.wraps(func)
            async def async_wrapper(*args, **kwargs):
                start = time.time()
                try:
                    result = await func(*args, **kwargs)
                    duration_ms = (time.time() - start) * 1000
                    logger.debug(f"✓ {op_name}: {duration_ms:.1f}ms")
                    return result
                except Exception as e:
                    duration_ms = (time.time() - start) * 1000
                    logger.error(f"✗ {op_name}: {duration_ms:.1f}ms - {e}")
                    raise

            return async_wrapper

        return wrapper

    return decorator


# ==============================================================================
# EXPLANATION & DESCRIPTION GENERATION
# ==============================================================================

class ExplanationGenerator:
    """Generates human-readable explanations for decisions."""

    @staticmethod
    def explain_occupancy(occupancy_rate: float) -> str:
        """Generate explanation for occupancy level."""
        level = OccupancyCalculator.get_occupancy_level(occupancy_rate)
        percentage = int(occupancy_rate * 100)
        return f"{level} occupancy ({percentage}%)"

    @staticmethod
    def explain_price_multiplier(multiplier: float, base_price: float) -> str:
        """Generate explanation for price multiplier."""
        percentage_change = int((multiplier - 1) * 100)
        final_price = base_price * multiplier

        if multiplier < 0.95:
            return f"Heavy discount: {percentage_change}% off, Final price: ₹{final_price:.0f}"
        elif multiplier < 1.0:
            return f"Discount: {abs(percentage_change)}% off, Final price: ₹{final_price:.0f}"
        elif multiplier < 1.05:
            return f"Standard pricing: Final price: ₹{final_price:.0f}"
        elif multiplier < 1.2:
            return f"Premium: {percentage_change}% markup, Final price: ₹{final_price:.0f}"
        else:
            return f"High demand: {percentage_change}% markup, Final price: ₹{final_price:.0f}"

    @staticmethod
    def explain_seat_allocation(success: bool, seats_count: int, message: str = "") -> str:
        """Generate explanation for seat allocation result."""
        if success:
            return f"Successfully allocated {seats_count} seat(s). {message}"
        else:
            return f"Could not allocate all seats. {message}"

    @staticmethod
    def factors_to_string(factors: Dict[str, float]) -> str:
        """Convert factors dictionary to readable string."""
        if not factors:
            return "No factors applied"

        parts = []
        for name, value in factors.items():
            percentage = int((value - 1) * 100) if abs(value - 1) > 0.01 else 0
            if percentage > 0:
                parts.append(f"{name} (+{percentage}%)")
            elif percentage < 0:
                parts.append(f"{name} ({percentage}%)")

        return ", ".join(parts) if parts else "Standard factors"


# ==============================================================================
# DATA VALIDATION UTILITIES
# ==============================================================================

class DataValidator:
    """Common data validation functions."""

    @staticmethod
    def validate_date(value) -> bool:
        """Validate date value."""
        try:
            if isinstance(value, date):
                return True
            elif isinstance(value, str):
                datetime.fromisoformat(value)
                return True
            return False
        except:
            return False

    @staticmethod
    def validate_quote(value: str) -> bool:
        """Validate railway booking quote/quota type."""
        valid_quotes = ['general', 'tatkal', 'premium', 'senior_citizen', 'ladies', 'pwd']
        return value.lower() in valid_quotes

    @staticmethod
    def validate_occupancy_rate(value: float) -> bool:
        """Validate occupancy rate is between 0 and 1."""
        try:
            rate = float(value)
            return 0.0 <= rate <= 1.0
        except:
            return False

    @staticmethod
    def validate_price(value: float) -> bool:
        """Validate price is positive."""
        try:
            return float(value) > 0
        except:
            return False
