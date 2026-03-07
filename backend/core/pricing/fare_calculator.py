import math
from typing import Dict, Set, Optional, List

# ==============================================================================
# IRCTC-GRADE FARE CONFIGURATION (from doc/COMPLETE_WORKFLOW_PIPELINE.md)
# ==============================================================================

# Base Fare per 100KM
BASE_FARE_PER_100KM = {
    "2S": 40.0,
    "SL": 55.0,
    "3A": 150.0,
    "3E": 130.0,
    "2A": 220.0,
    "1A": 380.0,
    "CC": 120.0,
    "EC": 250.0
}

# Mapping for standardization
COACH_MAP = {
    "AC_THREE_TIER": "3A",
    "AC_TWO_TIER": "2A",
    "AC_FIRST_CLASS": "1A",
    "SLEEPER": "SL",
    "CHAIR_CAR": "CC",
    "EXECUTIVE_CHAIR": "EC",
    "SECOND_SITTING": "2S",
    "3AC_ECONOMY": "3E"
}

def calculate_fare(
    distance_km: float, 
    coach: str, 
    is_tatkal: bool = False,
    concession_type: Optional[str] = None,
    is_multi_leg: bool = False,
    passengers: List[Dict] = None
) -> Dict[str, float]:
    """
    Implements the 7-step IRCTC Fare Algorithm.
    [39.5] Handles multiple passengers and discounts.
    """
    coach_code = COACH_MAP.get(coach, coach)
    base_rate = BASE_FARE_PER_100KM.get(coach_code, 150.0)

    # 1. Base Fare Calculation per 100KM
    unit_base_fare = (distance_km / 100.0) * base_rate

    # 2. Surcharge Application
    surcharge_multiplier = 1.15 if distance_km > 100 else 1.10 if distance_km > 50 else 1.0
    unit_base_fare *= surcharge_multiplier

    # [38.2] Telescopic Adjustment
    if is_multi_leg and distance_km > 500:
        unit_base_fare *= 0.95

    # 3. Multi-Passenger Logic (Subtask 39.5)
    passengers = passengers or [{"age": 30}] # Default 1 adult
    total_base = 0.0
    
    for p in passengers:
        age = p.get("age", 30)
        p_base = unit_base_fare
        
        # Senior Citizen (Female 58+, Male 60+) - Simplified to 60+
        if age >= 60:
            p_base *= 0.60 # 40% discount
        # Child (Under 5: Free, 5-12: Half)
        elif age < 5:
            p_base = 0.0
        elif age < 12:
            p_base *= 0.50
            
        total_base += p_base

    # 4. Tatkal Charge (10%)
    tatkal_charge = (total_base * 0.10) if is_tatkal else 0.0

    # 5. GST Calculation (5% for AC classes)
    is_ac = coach_code in ["3A", "3E", "2A", "1A", "CC", "EC"]
    gst = (total_base + tatkal_charge) * 0.05 if is_ac else 0.0

    # 6. Final Total
    total_fare = total_base + tatkal_charge + gst
    
    return {
        "base_fare": round(total_base, 2),
        "tatkal_charge": round(tatkal_charge, 2),
        "gst": round(gst, 2),
        "total_fare": math.ceil(total_fare)
    }

def calculate_unlock_fee() -> float:
    """
    Subtask 41.2: Fixed platform fee for unlocking journey details.
    """
    return 49.0

def calculate_agent_fee() -> float:
    """
    Subtask 42.2: Fixed agent commission for manual fulfillment.
    """
    return 10.0
