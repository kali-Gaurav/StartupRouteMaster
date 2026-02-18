"""
Input validation and sanitization utilities.
"""
import re
import logging
from datetime import datetime, date, timedelta
from typing import Optional, List

logger = logging.getLogger(__name__)


def validate_date_string(date_str: str, allow_past: bool = False) -> Optional[date]:
    """
    Validate and parse a date string in YYYY-MM-DD format.
    
    Args:
        date_str: Date string to validate
        allow_past: If False, reject dates in the past
        
    Returns:
        date object if valid, None otherwise
    """
    try:
        parsed_date = datetime.fromisoformat(date_str).date()
        
        if not allow_past:
            today = datetime.utcnow().date()
            if parsed_date < today:
                logger.warning(f"Date is in the past: {date_str}")
                return None
        
        return parsed_date
    except (ValueError, TypeError) as e:
        logger.warning(f"Invalid date format: {date_str} ({e})")
        return None


def validate_station_name(name: str) -> Optional[str]:
    """
    Validate and sanitize station name.
    
    Args:
        name: Station name to validate
        
    Returns:
        Sanitized name if valid, None otherwise
    """
    if not name or not isinstance(name, str):
        return None
    
    clean_name = name.strip()
    
    # Check length
    if len(clean_name) < 2 or len(clean_name) > 255:
        logger.warning(f"Station name out of bounds: {name}")
        return None
    
    # Allow letters, numbers, spaces, hyphens, parentheses, dots
    # This accommodates station names like "New Delhi Junction" or "St. Pancras"
    if not re.match(r"^[a-zA-Z0-9\s\-().,]*$", clean_name):
        logger.warning(f"Station name contains invalid characters: {name}")
        return None
    
    return clean_name


def validate_budget_category(budget: str) -> Optional[str]:
    """
    Validate budget category.
    
    Args:
        budget: Budget category string
        
    Returns:
        Validated budget string or None
    """
    valid_categories = ["all", "economy", "standard", "premium"]
    
    if budget not in valid_categories:
        logger.warning(f"Invalid budget category: {budget}")
        return None
    
    return budget


def validate_passenger_type(ptype: str) -> Optional[str]:
    """
    Validate passenger type.
    
    Args:
        ptype: Passenger type string
        
    Returns:
        Validated passenger type or None
    """
    valid_types = ["adult", "child", "senior", "student"]
    
    if ptype not in valid_types:
        logger.warning(f"Invalid passenger type: {ptype}")
        return None
    
    return ptype


def validate_concessions(concessions: Optional[List[str]]) -> Optional[List[str]]:
    """
    Validate concession list.
    
    Args:
        concessions: List of concession codes
        
    Returns:
        Validated concession list or None
    """
    if not concessions:
        return []
    
    valid_concessions = [
        "defence",
        "freedom_fighter",
        "divyang",  # Person with disability
        "senior_citizen",
        "student",
        "clergy",
    ]
    
    validated = []
    for concession in concessions:
        if concession.lower() in valid_concessions:
            validated.append(concession.lower())
        else:
            logger.warning(f"Invalid concession: {concession}")
    
    return validated


def validate_gender(gender: str) -> Optional[str]:
    """
    Validate gender value.
    
    Args:
        gender: Gender string
        
    Returns:
        Validated gender or None
    """
    valid_genders = ["M", "F", "O"]  # Male, Female, Other
    
    if gender.upper() not in valid_genders:
        logger.warning(f"Invalid gender: {gender}")
        return None
    
    return gender.upper()


def validate_age(age: int) -> bool:
    """
    Validate passenger age.
    
    Args:
        age: Age in years
        
    Returns:
        True if valid, False otherwise
    """
    if not isinstance(age, int) or age < 0 or age > 150:
        logger.warning(f"Invalid age: {age}")
        return False
    
    return True


def validate_phone_number(phone: str) -> Optional[str]:
    """
    Validate phone number (Indian format).
    
    Args:
        phone: Phone number string
        
    Returns:
        Cleaned phone number or None
    """
    # Remove common separators
    clean_phone = re.sub(r"[\s\-()]+", "", phone)
    
    # Indian phone numbers: 10 digits
    if not re.match(r"^[6-9]\d{9}$", clean_phone):
        logger.warning(f"Invalid phone number: {phone}")
        return None
    
    return clean_phone


def validate_email(email: str) -> bool:
    """
    Basic email validation returning boolean (True if valid, False otherwise).

    This aligns the validator with other `validate_*` functions used across tests.
    """
    if not email or not isinstance(email, str):
        logger.warning(f"Invalid email: {email}")
        return False

    pattern = r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$"

    if not re.match(pattern, email):
        logger.warning(f"Invalid email: {email}")
        return False

    return True


class SearchRequestValidator:
    """Comprehensive validator for search requests."""
    
    def __init__(self):
        self.errors: List[str] = []
    
    def validate(self, source: str, destination: str, date_str: str, 
                 budget: str = "all", journey_type: str = "single",
                 passenger_type: str = "adult", concessions: Optional[List[str]] = None) -> bool:
        """
        Validate complete search request.
        
        Returns:
            True if valid, False otherwise
        """
        self.errors = []
        
        # Station names
        if not validate_station_name(source):
            self.errors.append(f"Invalid source station: {source}")
        
        if not validate_station_name(destination):
            self.errors.append(f"Invalid destination station: {destination}")
        
        if source == destination:
            self.errors.append("Source and destination cannot be the same")
        
        # Date
        if not validate_date_string(date_str):
            self.errors.append(f"Invalid travel date: {date_str}")
        
        # Budget
        if not validate_budget_category(budget):
            self.errors.append(f"Invalid budget category: {budget}")
        
        # Passenger type
        if not validate_passenger_type(passenger_type):
            self.errors.append(f"Invalid passenger type: {passenger_type}")
        
        # Concessions
        if concessions:
            validated_concessions = validate_concessions(concessions)
            if len(validated_concessions) < len(concessions):
                self.errors.append(f"Some concessions are invalid")
        
        return len(self.errors) == 0
    
    def get_errors(self) -> List[str]:
        """Get list of validation errors."""
        return self.errors
    
    def get_error_message(self) -> str:
        """Get comma-separated error message."""
        return "; ".join(self.errors) if self.errors else "Validation passed"
