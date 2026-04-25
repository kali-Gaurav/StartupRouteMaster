import math
import logging
import numpy as np
from typing import Any, Dict, Optional, List
from sqlalchemy import text

logger = logging.getLogger(__name__)

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

def get_slab_fare(db, coach_code: str, distance: float) -> float:
    """[7.3] IRCTC Telescopic Slab Lookup."""
    try:
        # 1. Exact Slab Match
        query = text("""
            SELECT base_fare FROM fare_slabs 
            WHERE class_code = :c 
              AND :d BETWEEN min_km AND max_km 
            LIMIT 1
        """)
        res = db.execute(query, {"c": coach_code, "d": int(distance)}).fetchone()
        if res: return float(res[0])
        
        # 2. Fallback to Incremental (Distance > Max Slab)
        # Find the highest slab for this class
        max_slab_query = text("""
            SELECT max_km, base_fare FROM fare_slabs 
            WHERE class_code = :c 
            ORDER BY max_km DESC LIMIT 1
        """)
        max_row = db.execute(max_slab_query, {"c": coach_code}).fetchone()
        
        if not max_row:
            return distance * 1.5 # Extreme fallback
            
        max_km, max_base = float(max_row[0]), float(max_row[1])
        
        # Get incremental rate from matrix
        query_inc = text("SELECT base_fare_per_km FROM class_fare_matrix WHERE class_code = :c")
        res_inc = db.execute(query_inc, {"c": coach_code}).fetchone()
        rate = float(res_inc[0]) if res_inc else 1.5
        
        return max_base + (max(0, distance - max_km) * rate)
    except Exception as e:
        logger.error(f"Slab lookup failed: {e}")
        return distance * 1.5 

def calculate_fare(
    distance_km: float,
    coach: str,
    is_tatkal: bool = False,
    passengers: Optional[List[Dict[str, Any]]] = None,
    db = None
) -> Dict[str, Any]:
    """
    [7.1-7.10] Production-Grade IRCTC Telescopic Pricing Engine.
    """
    # [7.8] Zero distance handling
    if distance_km <= 0:
        return {"base_fare": 0, "tatkal_charge": 0, "gst": 0, "total_fare": 0}

    coach_code = COACH_MAP.get(coach, coach)
    
    # 1. Base Fare from Slabs (Subtask 7.3)
    if db:
        unit_base_fare = get_slab_fare(db, coach_code, distance_km)
    else:
        # Fallback to rough linear if DB session not provided
        base_rates = {"SL": 0.6, "3A": 1.5, "2A": 2.2, "1A": 4.5}
        rate = base_rates.get(coach_code, 1.5)
        unit_base_fare = 175.0 + (max(0, distance_km - 300) * rate)

    # 2. Multi-Passenger Logic (Subtask 7.7)
    passengers = passengers or [{"age": 30}]
    total_base = 0.0
    
    for p in passengers:
        age = int(p.get("age", 30))
        p_base = unit_base_fare
        
        # [7.7] Concession logic
        if age >= 60: # Senior
            p_base *= 0.60
        elif age < 5: # Child free
            p_base = 0.0
        elif age < 12: # Child half
            p_base *= 0.50
            
        total_base += p_base

    # 3. [7.5] Tatkal Premium (10% or min/max caps)
    tatkal_charge = 0.0
    if is_tatkal:
        # Simplified: 10% of base fare
        tatkal_charge = total_base * 0.10
        # IRCTC has min/max caps per class (e.g. SL min 100, 3A min 300)
        min_tatkal = {"SL": 100, "3A": 300, "2A": 400, "1A": 400}.get(coach_code, 100)
        tatkal_charge = max(tatkal_charge, min_tatkal)

    # 4. [7.6] GST (5% for AC)
    is_ac = coach_code in ["3A", "3E", "2A", "1A", "CC", "EC"]
    gst = (total_base + tatkal_charge) * 0.05 if is_ac else 0.0

    # 5. [7.9] Minimum Fare enforcement (Rs. 30)
    total_fare = total_base + tatkal_charge + gst
    if total_fare > 0:
        total_fare = max(30.0, total_fare)

    # 6. [7.10, 7.18] Rounded Breakdown
    return {
        "base_fare": round(total_base, 2),
        "tatkal_charge": round(tatkal_charge, 2),
        "gst": round(gst, 2),
        "total_fare": math.ceil(total_fare), # [7.18] Standard rounding
        "distance": round(distance_km, 2),
        "class": coach_code
    }

def calculate_fares_batch(distances: np.ndarray, coach_class: str, is_tatkal: bool = False, db=None) -> np.ndarray:
    """[Task 28.2] Vectorized batch fare calculation using numpy."""
    rates = {"SL": 0.6, "3A": 1.2, "2A": 2.5, "1A": 4.5}
    rate = rates.get(coach_class, 0.6)
    base_fares = distances * rate
    agent_fee = 10.0
    tatkal_charge = 150.0 if is_tatkal else 0.0
    total_fares = base_fares + agent_fee + tatkal_charge
    return np.round(total_fares, 2)

def calculate_unlock_fee(db=None) -> float:
    """[7.11] Link fees to PlatformConfig."""
    if db:
        try:
            res = db.execute(text("SELECT value FROM platform_configs WHERE key = 'UNLOCK_FEE'")).fetchone()
            if res: return float(res[0])
        except: pass
    return 49.0

def calculate_agent_fee(db=None) -> float:
    if db:
        try:
            res = db.execute(text("SELECT value FROM platform_configs WHERE key = 'AGENT_FEE'")).fetchone()
            if res: return float(res[0])
        except: pass
    return 10.0
