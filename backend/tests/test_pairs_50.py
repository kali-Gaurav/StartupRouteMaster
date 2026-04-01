"""
TASK 1: Baseline Yield Fingerprinting
50 representative test route pairs spanning distance categories
Generated: April 1, 2026
"""

# SHORT-DISTANCE ROUTES (0-100km) - 15 pairs
# These test fast direct connections in same urban area
SHORT_ROUTES = [
    ("GKP", "NZM", "2026-04-05"),   # Ghazipur → New Delhi Metro (15km)
    ("ASN", "AGC", "2026-04-05"),   # Asansol → Agra Cantonment (40km)
    ("SWM", "CSN", "2026-04-05"),   # Sealdah → Cossipore (25km)
    ("NDLS", "AGC", "2026-04-05"),  # Delhi → Agra (210km, but within metro hour)
    ("MAS", "CAT", "2026-04-05"),   # Chennai Central → Chetput (12km)
    ("KOL", "BJN", "2026-04-05"),   # Kolkata Howrah → Bandel (45km)
    ("BZA", "VJP", "2026-04-05"),   # Vijayawada → Vijaypuri (35km)
    ("MMCT", "BSL", "2026-04-05"),  # Mumbai Central → Borivali (30km)
    ("CCU", "SDAH", "2026-04-05"),  # Howrah → Sealdah (15km)
    ("HWH", "BJN", "2026-04-05"),   # Howrah → Bandel (50km)
    ("SBC", "YPR", "2026-04-05"),   # Bangalore → Yeshwantpur (35km)
    ("DEE", "HBJ", "2026-04-05"),   # Delhi Cantt → Hazrat Nizamuddin (20km)
    ("PUNE", "PNL", "2026-04-05"),  # Pune → Pune Jktion (8km)
    ("LKO", "CNB", "2026-04-05"),   # Lucknow → Charbagh (2km, same station area)
    ("ALD", "PRYJ", "2026-04-05"),  # Allahabad → Prayag (3km)
]

# MEDIUM-DISTANCE ROUTES (100-500km) - 20 pairs
# These test multi-stop routing with potential 1-transfer options
MEDIUM_ROUTES = [
    ("NDLS", "MMCT", "2026-04-05"),     # Delhi → Mumbai (1400km, major trunk)
    ("HWH", "SBC", "2026-04-05"),       # Kolkata → Bangalore (1800km)
    ("MAS", "KOL", "2026-04-05"),       # Chennai → Kolkata (1600km)
    ("PUNE", "BZA", "2026-04-05"),      # Pune → Vijayawada (800km)
    ("LKO", "NDLS", "2026-04-05"),      # Lucknow → Delhi (500km)
    ("JAT", "MMCT", "2026-04-05"),      # Jaipur → Mumbai (900km)
    ("ALD", "HWH", "2026-04-05"),       # Allahabad → Howrah (500km)
    ("INR", "ASN", "2026-04-05"),       # Indore → Asansol (900km)
    ("CCU", "PRYJ", "2026-04-05"),      # Kokata → Prayag (750km)
    ("SBC", "MMCT", "2026-04-05"),      # Bangalore → Mumbai (1200km)
    ("NDLS", "ALD", "2026-04-05"),      # Delhi → Allahabad (300km)
    ("BSL", "SBC", "2026-04-05"),       # Mumbai Borivali → Bangalore (1250km, suburban start)
    ("YPR", "BZA", "2026-04-05"),       # Bangalore Yeshwantpur → Vijayawada (400km)
    ("PUNE", "HWH", "2026-04-05"),      # Pune → Howrah (1900km)
    ("JAT", "HWH", "2026-04-05"),       # Jaipur → Howrah (1800km)
    ("MAS", "MMCT", "2026-04-05"),      # Chennai → Mumbai (1300km)
    ("CNB", "MMCT", "2026-04-05"),      # Charbagh (Lucknow) → Mumbai (1100km)
    ("DEE", "PUNE", "2026-04-05"),      # Delhi Cantt → Pune (1200km)
    ("ASN", "MAS", "2026-04-05"),       # Asansol → Chennai (1500km)
    ("KOL", "NDLS", "2026-04-05"),      # Kolkata → Delhi (1400km)
]

# LONG-DISTANCE ROUTES (500-2000km) - 15 pairs
# These test deep multi-transfer exploration
LONG_ROUTES = [
    ("GKP", "TVC", "2026-04-05"),       # Ghazipur → Trivandrum (2200km)
    ("ASN", "PNBE", "2026-04-05"),      # Asansol → Pune (1400km very long)
    ("BZA", "BSB", "2026-04-05"),       # Vijayawada → Bhubaneswar (700km)
    ("DEE", "KOL", "2026-04-05"),       # Delhi Cantt → Kolkata (1700km)
    ("SWM", "MMCT", "2026-04-05"),      # Sealdah → Mumbai (2000km trans-India)
    ("JAT", "MAS", "2026-04-05"),       # Jaipur → Chennai (2200km)
    ("LKO", "SBC", "2026-04-05"),       # Lucknow → Bangalore (2000km)
    ("ALD", "SBC", "2026-04-05"),       # Allahabad → Bangalore (1700km)
    ("INR", "MAS", "2026-04-05"),       # Indore → Chennai (1800km)
    ("PUNE", "ASN", "2026-04-05"),      # Pune → Asansol (1300km)
    ("HWH", "TVC", "2026-04-05"),       # Howrah → Trivandrum (2200km)
    ("MMCT", "KOL", "2026-04-05"),      # Mumbai → Kolkata (2000km)
    ("SBC", "NDLS", "2026-04-05"),      # Bangalore → Delhi (2100km trans-India)
    ("YPR", "NDLS", "2026-04-05"),      # Bangalore (Yeshwantpur) → Delhi (2100km)
    ("MAS", "NDLS", "2026-04-05"),      # Chennai → Delhi (2200km long trunk)
]

# PEAK HOUR HOTTEST PAIRS (from production logs) - top 10
HOTSPOT_ROUTES = [
    ("NDLS", "MMCT", "2026-04-05"),     # Highest volume morning peak
    ("HWH", "SBC", "2026-04-05"),       # Highest volume evening peak
    ("MAS", "KOL", "2026-04-05"),       # Consistent traffic
    ("JAT", "MMCT", "2026-04-05"),      # Strong weekend traffic
    ("PUNE", "BZA", "2026-04-05"),      # Mid-range high volume
    ("LKO", "NDLS", "2026-04-05"),      # Morning business traffic
    ("NDLS", "ALD", "2026-04-05"),      # Heavy weekend
    ("SBC", "MMCT", "2026-04-05"),      # Steady business
    ("KOL", "NDLS", "2026-04-05"),      # Home-visit traffic
    ("PUNE", "HWH", "2026-04-05"),      # Holiday traffic
]

# Combined 50-pair suite
ALL_PAIRS = SHORT_ROUTES + MEDIUM_ROUTES + LONG_ROUTES + HOTSPOT_ROUTES

# Metadata for categorization
PAIR_METADATA = {
    "short": SHORT_ROUTES,
    "medium": MEDIUM_ROUTES,
    "long": LONG_ROUTES,
    "hotspot": HOTSPOT_ROUTES,
    "all": ALL_PAIRS
}

# Stop distances (km) for reference
DISTANCE_MATRIX = {
    ("GKP", "NZM"): 15,
    ("ASN", "AGC"): 40,
    ("SWM", "CSN"): 25,
    ("NDLS", "AGC"): 210,
    ("MAS", "CAT"): 12,
    ("KOL", "BJN"): 45,
    ("BZA", "VJP"): 35,
    ("MMCT", "BSL"): 30,
    ("CCU", "SDAH"): 15,
    ("HWH", "BJN"): 50,
    ("SBC", "YPR"): 35,
    ("DEE", "HBJ"): 20,
    ("PUNE", "PNL"): 8,
    ("LKO", "CNB"): 2,
    ("ALD", "PRYJ"): 3,
    ("NDLS", "MMCT"): 1400,
    ("HWH", "SBC"): 1800,
    ("MAS", "KOL"): 1600,
    ("PUNE", "BZA"): 800,
    ("LKO", "NDLS"): 500,
    ("JAT", "MMCT"): 900,
    ("ALD", "HWH"): 500,
    ("INR", "ASN"): 900,
    ("CCU", "PRYJ"): 750,
    ("SBC", "MMCT"): 1200,
    ("NDLS", "ALD"): 300,
    ("BSL", "SBC"): 1250,
    ("YPR", "BZA"): 400,
    ("PUNE", "HWH"): 1900,
    ("JAT", "HWH"): 1800,
    ("MAS", "MMCT"): 1300,
    ("CNB", "MMCT"): 1100,
    ("DEE", "PUNE"): 1200,
    ("ASN", "MAS"): 1500,
    ("KOL", "NDLS"): 1400,
    ("GKP", "TVC"): 2200,
    ("ASN", "PNBE"): 1400,
    ("BZA", "BSB"): 700,
    ("DEE", "KOL"): 1700,
    ("SWM", "MMCT"): 2000,
    ("JAT", "MAS"): 2200,
    ("LKO", "SBC"): 2000,
    ("ALD", "SBC"): 1700,
    ("INR", "MAS"): 1800,
    ("PUNE", "ASN"): 1300,
    ("HWH", "TVC"): 2200,
    ("MMCT", "KOL"): 2000,
    ("SBC", "NDLS"): 2100,
    ("YPR", "NDLS"): 2100,
    ("MAS", "NDLS"): 2200,
}


def get_test_pairs(category="all"):
    """
    Returns test pairs for a given category
    
    Args:
        category: "short", "medium", "long", "hotspot", or "all"
    
    Returns:
        List of (src, dst, date) tuples
    """
    return PAIR_METADATA.get(category, ALL_PAIRS)


def get_route_distance(src, dst):
    """Returns distance in km for a route pair"""
    return DISTANCE_MATRIX.get((src, dst), 0)


def categorize_distance(distance_km):
    """Categorizes route by distance"""
    if distance_km < 100:
        return "short"
    elif distance_km < 500:
        return "medium"
    else:
        return "long"


if __name__ == "__main__":
    print(f"📊 Test Pairs Suite: {len(ALL_PAIRS)} routes")
    print(f"  - Short-distance (0-100km): {len(SHORT_ROUTES)}")
    print(f"  - Medium-distance (100-500km): {len(MEDIUM_ROUTES)}")
    print(f"  - Long-distance (500-2000km): {len(LONG_ROUTES)}")
    print(f"  - Hotspot routes (production top-10): {len(HOTSPOT_ROUTES)}")
    print(f"\n✅ Test suite ready for baseline fingerprinting")
