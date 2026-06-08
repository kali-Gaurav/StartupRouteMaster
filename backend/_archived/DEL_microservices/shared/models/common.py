
from enum import Enum
from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field
from datetime import datetime

class Persona(str, Enum):
    EMERGENCY = "emergency"
    COMFORT = "comfort"
    BUDGET = "budget"
    ECONOMY = "economy"
    STANDARD = "standard"
    PREMIUM = "premium"
    FAMILY = "family"

class QuotaType(str, Enum):
    GENERAL = "GN"
    TATKAL = "TQ"
    PREMIUM_TATKAL = "PT"
    LADIES = "LD"
    SENIOR_CITIZEN = "SS"
    PERSON_WITH_DISABILITY = "HP"

class PaginationMetadata(BaseModel):
    total_results: int
    current_page: int
    limit: int
    has_next: bool
    total_pages: int
