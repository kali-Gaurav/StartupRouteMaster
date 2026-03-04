from typing import Dict, Any

class FareCalculator:
    """
    Calculates approximate fares based on distance and travel class.
    Rates are based on Indian Railway general averages.
    """
    
    # Rates per KM (approximate)
    RATES = {
        "SL": 0.6,
        "3A": 1.5,
        "2A": 2.2,
        "1A": 3.8,
        "CC": 1.2,
        "2S": 0.3
    }
    
    # Base reservation/other charges
    BASE_FEES = {
        "SL": 20,
        "3A": 40,
        "2A": 50,
        "1A": 60,
        "CC": 40,
        "2S": 15
    }

    @staticmethod
    def calculate(distance_km: float, travel_class: str) -> float:
        """
        Returns estimated fare in INR.
        """
        cls = travel_class.upper()
        rate = FareCalculator.RATES.get(cls, 0.5)
        base = FareCalculator.BASE_FEES.get(cls, 20)
        
        # Simple linear model: (dist * rate) + base fee
        # Minimum distance charging usually applies (not implemented for simplicity)
        estimated_fare = (distance_km * rate) + base
        
        return round(estimated_fare, 2)

    @staticmethod
    def get_supported_classes() -> list:
        return list(FareCalculator.RATES.keys())
