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
    concession_type: Optional[str] = None
) -> Dict[str, float]:
    """
    Implements the 7-step IRCTC Fare Algorithm from the System Blueprint.
    """
    coach_code = COACH_MAP.get(coach, coach)
    base_rate = BASE_FARE_PER_100KM.get(coach_code, 150.0)

    # 1. Base Fare Calculation
    base_fare = (distance_km / 100.0) * base_rate

    # 2. Surcharge Application
    if distance_km > 100:
        surcharge_multiplier = 1.15  # 15% extra
    elif distance_km > 50:
        surcharge_multiplier = 1.10  # 10% extra
    else:
        surcharge_multiplier = 1.0
    
    base_fare_with_surcharge = base_fare * surcharge_multiplier

    # 3. Tatkal Charge (10%)
    tatkal_charge = (base_fare_with_surcharge * 0.10) if is_tatkal else 0.0

    # 4. GST Calculation (5% for AC classes)
    is_ac = coach_code in ["3A", "3E", "2A", "1A", "CC", "EC"]
    gst = (base_fare_with_surcharge + tatkal_charge) * 0.05 if is_ac else 0.0

    # 5. Concessions (e.g., student 25%)
    concession_discount = 0.0
    if concession_type == "student":
        concession_discount = base_fare_with_surcharge * 0.25
    
    # 6. Final Total
    total_fare = (base_fare_with_surcharge - concession_discount) + tatkal_charge + gst
    
    return {
        "base_fare": round(base_fare_with_surcharge, 2),
        "tatkal_charge": round(tatkal_charge, 2),
        "gst": round(gst, 2),
        "concession_discount": round(concession_discount, 2),
        "total_fare": math.ceil(total_fare) # Round up to nearest rupee
    }
