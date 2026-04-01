"""
Hub Definitions - Task 6: Hub-Only Routing Fallback
Major Indian Railway Hubs for multi-modal/multi-train connectivity.
"""

from typing import List, Dict

# [6.1] Major Railway Hubs in India (A1 Tier - MEGA HUBS)
MEGA_HUBS = {
    "NDLS", "HWH", "MAS", "CSMT", "LKO", "DDU", "PNBE", "SC", "SBC", "ADI", "JP"
}

# (Tier 1 - MAJOR HUBS)
MAJOR_HUBS = {
    "BRC", "CNB", "KGP", "VGLJ", "BPL", "AGC", "BSB", "ET", "NGP", "MTJ",
    "PGT", "KOTA", "GHY", "PUNE", "MMCT", "BCT", "NZM", "TATA", "JSG", "VSKP", "NED"
}

# (Tier 2 - REGIONAL HUBS)
REGIONAL_HUBS = {
    "R", "BSP", "REWA", "JBP", "STA", "BINA", "BKN", "BME", "RE", "GKP", "GD", "CPR"
}


# Hub coordinates for proximity search (Simplified mapping)
HUB_COORDINATES = {
    "NDLS": (28.6422, 77.2187),
    "HWH": (22.5836, 88.3415),
    "MAS": (13.0827, 80.2707),
    "CSMT": (18.9400, 72.8353),
    "BRC": (22.3106, 73.1812),
    "CNB": (26.4547, 80.3507),
    "PNBE": (25.6022, 85.1376),
    "KGP": (22.3301, 87.3237),
    "BPL": (23.2599, 77.4126),
    "JP": (26.9196, 75.7878),
    "ADI": (23.0225, 72.5714),
    "SC": (17.4399, 78.5020),
    "SBC": (12.9779, 77.5779),
    "BSB": (25.3176, 82.9739),
    "NGP": (21.1458, 79.0882),
    "LKO": (26.8467, 80.9462),
    "PGT": (10.7867, 76.6547),
    "KOTA": (25.2138, 75.8648),
    "GHY": (26.1812, 91.7495),
    "PUNE": (18.5284, 73.8739),
    "MMCT": (18.9696, 72.8193),
    "NZM": (28.5889, 77.2530)
}

def get_hubs_near(lat: float, lon: float, limit: int = 3) -> List[str]:
    """[6.3] Find closest hubs using Euclidean distance (proxy for Haversine here)."""
    distances = []
    for hub, coords in HUB_COORDINATES.items():
        dist = ((lat - coords[0])**2 + (lon - coords[1])**2)**0.5
        distances.append((hub, dist))
    
    # Sort by distance
    distances.sort(key=lambda x: x[1])
    return [d[0] for d in distances[:limit]]

def get_smart_transfer_buffer(station_code: str, reliability_score: float = 0.5) -> int:
    """[Task 143] Scaled Transfer Time based on Hub size and Arrival Punctuality."""
    # Base transfer time by tier
    if station_code in MEGA_HUBS:
        base = 40  # 40 mins for mega hubs (complex platform changes)
    elif station_code in MAJOR_HUBS:
        base = 25  # 25 mins for major junctions
    elif station_code in REGIONAL_HUBS:
        base = 15
    else:
        base = 15
        
    # [Task 143.2] Reliability Buffer
    # Score 0.5 is neutral. < 0.5 means train is often late.
    # Buffer scales linearly: 0.0 reliability (+30m), 1.0 reliability (-5m)
    rel_adj = (0.5 - reliability_score) * 60
    rel_adj = max(-5, min(30, rel_adj))
    
    # Ensuring minimum safety threshold of 15 mins
    return int(max(15, base + rel_adj))
