import math
from typing import Dict, Set, Optional
from sqlalchemy import func

# ==============================================================================
# INDIAN RAILWAYS FARE CONFIGURATION
# ==============================================================================

# Base fare per KM (Approx realistic IR values)
FARE_RATES = {
    "2S": 0.40,
    "SL": 0.55,
    "3A": 1.60,
    "3E": 1.40,
    "2A": 2.40,
    "1A": 4.00,
    "CC": 1.30,
    "EC": 2.60
}

# Reservation Charges (Fixed)
RESERVATION_CHARGES = {
    "2S": 15,
    "SL": 20,
    "3A": 40,
    "3E": 40,
    "2A": 50,
    "1A": 60,
    "CC": 40,
    "EC": 60
}

# Superfast Charges (Fixed)
SUPERFAST_CHARGES = {
    "2S": 10,
    "SL": 30,
    "3A": 45,
    "3E": 45,
    "2A": 45,
    "1A": 75,
    "CC": 45,
    "EC": 75
}

# Classes that attract GST (5%)
AC_CLASSES: Set[str] = {"3A", "3E", "2A", "1A", "CC", "EC", "AC_THREE_TIER", "AC_TWO_TIER", "AC_FIRST_CLASS", "CHAIR_CAR", "EXECUTIVE_CHAIR"}

# Mapping from standard names to IR codes
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
    is_superfast: bool = True, 
    is_tatkal: bool = False,
    demand_factor: float = 1.0,
    include_catering: bool = False,
    catering_charge: float = 0.0
) -> Dict[str, float]:
    """
    Calculates the fare based on distance, coach type, and other factors.
    Returns a breakdown of the fare.
    """
    # Normalize coach code
    coach_code = COACH_MAP.get(coach, coach)
    
    if coach_code not in FARE_RATES:
        raise ValueError(f"Invalid coach type: {coach}")

    # 1. Distance Calculation (Slab rounding: ceil to nearest 10km)
    charged_distance = math.ceil(distance_km / 10) * 10
    
    # 2. Base Fare
    base_fare = charged_distance * FARE_RATES[coach_code]
    
    # 3. Tatkal Pricing (30% of base fare, minimum/maximum limits apply in reality, 
    # but using simplified 30% here as requested)
    if is_tatkal:
        tatkal_premium = base_fare * 0.3
        base_fare += tatkal_premium

    # 4. Reservation Charge
    reservation_charge = RESERVATION_CHARGES.get(coach_code, 0)
    
    # 5. Superfast Charge
    sf_charge = SUPERFAST_CHARGES.get(coach_code, 0) if is_superfast else 0
    
    # 6. Demand Factor (Dynamic Pricing)
    base_fare *= demand_factor
    
    # Subtotal before GST
    subtotal = base_fare + reservation_charge + sf_charge
    
    # 7. GST Calculation (5% for AC classes)
    gst = 0.0
    if coach_code in AC_CLASSES or coach in AC_CLASSES:
        gst = subtotal * 0.05
    
    # 8. Catering (Optional)
    final_catering_charge = catering_charge if include_catering else 0.0
    
    total_fare = subtotal + gst + final_catering_charge
    
    return {
        "base_fare": round(base_fare, 2),
        "reservation_charge": reservation_charge,
        "superfast_charge": sf_charge,
        "subtotal": round(subtotal, 2),
        "gst": round(gst, 2),
        "catering_charge": final_catering_charge,
        "total_fare": math.ceil(total_fare) # IRCTC usually rounds up to nearest whole rupee
    }

def get_fare_for_train(
    db_session,
    train_number: str,
    from_station_code: str,
    to_station_code: str,
    coach: str,
    is_tatkal: bool = False
) -> Optional[Dict[str, float]]:
    """
    Helper function to calculate fare for a specific train and station pair
    by looking up distance/cost in the active GTFS-based tables.
    """
    from database.models import Stop, StopTime, Trip, Route
    
    # 1. Find the trip using the train_number (GTFS trip_id)
    trip = db_session.query(Trip).filter(Trip.trip_id == train_number).first()
    if not trip:
        return None

    # 2. Find Stop objects to get their internal IDs
    from_stop = db_session.query(Stop).filter(Stop.stop_id == from_station_code).first()
    to_stop = db_session.query(Stop).filter(Stop.stop_id == to_station_code).first()
    if not from_stop or not to_stop:
        return None

    # 3. Find StopTime entries for this trip and these stops
    from_st = db_session.query(StopTime).filter(
        StopTime.trip_id == trip.id,
        StopTime.stop_id == from_stop.id
    ).first()
    
    to_st = db_session.query(StopTime).filter(
        StopTime.trip_id == trip.id,
        StopTime.stop_id == to_stop.id
    ).first()
    
    if not from_st or not to_st:
        return None
        
    # 4. Calculate total cost/distance based on StopTime segments
    # We sum the 'cost' field from all stops between 'from' and 'to' sequences
    # StopTime.cost represents the cost of the segment arriving at that stop.
    if from_st.stop_sequence < to_st.stop_sequence:
        # Normal direction: sum costs from (from_seq + 1) up to to_seq
        total_cost = db_session.query(func.sum(StopTime.cost)).filter(
            StopTime.trip_id == trip.id,
            StopTime.stop_sequence > from_st.stop_sequence,
            StopTime.stop_sequence <= to_st.stop_sequence
        ).scalar() or 0.0
    else:
        # Reverse direction if needed (usually trips are one-way in GTFS)
        return None
    
    # 5. Check if train is superfast (using route name/type as heuristic)
    is_sf = False
    if trip.route:
        name = (trip.route.long_name or "").upper()
        is_sf = any(x in name for x in ["SUPERFAST", "RAJ", "DUR", "SHATABDI", "SF"])
        
    # If the database 'cost' is 0, we fallback to a default distance-based calculation 
    # but since calculate_fare expects distance_km, we'll treat 'cost' as distance 
    # if it's in a reasonable range, or use a default if it's 0.
    # In this schema, 'cost' in StopTime often stores the base fare for that segment.
    if total_cost <= 0:
        return None

    # For IRCTC-like calculation, we often need distance. 
    # If total_cost is already the base fare, we can skip distance-based base fare calculation.
    # But for consistency with calculate_fare, let's assume total_cost is distance in km 
    # if it's coming from an ETL that populates it as such.
    return calculate_fare(total_cost, coach, is_superfast=is_sf, is_tatkal=is_tatkal)
