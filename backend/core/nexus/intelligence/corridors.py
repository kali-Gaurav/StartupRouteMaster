from datetime import date
from typing import List, Tuple

# [Task 105] Regional Intelligence: High-Demand Corridors & Festival Calendar
# Maps periods of extreme demand to specific geographic corridors.

FESTIVAL_CALENDAR = {
    "DIWALI": {"start": (10, 25), "end": (11, 10), "corridors": ["NORTH_BELT", "EAST_BELT"]},
    "HOLI": {"start": (3, 1), "end": (3, 20), "corridors": ["NORTH_BELT"]},
    "CHHATH_PUJA": {"start": (11, 5), "end": (11, 15), "corridors": ["EAST_BELT", "BIHAR_SPECIAL"]},
    "WEEKEND_SURGE": {"start": (1, 1), "end": (12, 31), "corridors": ["HILL_STATIONS", "METRO_LOOPS"]}
}

CORRIDOR_MAPPINGS = {
    "NORTH_BELT": [
        (1, 10), # Delhi -> Lucknow
        (1, 15), # Delhi -> Varanasi
        (1, 20)  # Delhi -> Patna
    ],
    "EAST_BELT": [
        (1, 30), # Delhi -> Howrah
        (2, 30), # Mumbai -> Howrah
    ],
    "METRO_LOOPS": [
        (1, 2),  # Delhi -> Mumbai
        (2, 1),  # Mumbai -> Delhi
        (2, 4),  # Mumbai -> Chennai
        (4, 2)   # Chennai -> Mumbai
    ],
    "BIHAR_SPECIAL": [
        (2, 20), # Mumbai -> Patna
        (1, 20), # Delhi -> Patna
        (4, 20)  # Chennai -> Patna
    ]
}

def get_active_corridors() -> List[str]:
    """Identifies which corridors are currently in peak demand."""
    today = date.today()
    active = ["METRO_LOOPS"] # Always active
    
    for event, data in FESTIVAL_CALENDAR.items():
        s_month, s_day = data["start"]
        e_month, e_day = data["end"]
        
        # Simple date range check (approximation)
        start_date = date(today.year, s_month, s_day)
        end_date = date(today.year, e_month, e_day)
        
        if start_date <= today <= end_date:
            active.extend(data["corridors"])
            
    return list(set(active))

def get_high_demand_pairs() -> List[Tuple[int, int]]:
    """Returns station pairs prioritized by the current festival/event calendar."""
    active_corridors = get_active_corridors()
    pairs = []
    for corridor in active_corridors:
        pairs.extend(CORRIDOR_MAPPINGS.get(corridor, []))
    return list(set(pairs))
