import logging
from typing import List

logger = logging.getLogger(__name__)

class RegionManager:
    """Manages regional partitioning of the national network"""
    
    REGIONS = {
        'North': ['Delhi', 'Punjab', 'Haryana', 'Himachal Pradesh', 'Jammu & Kashmir', 'Uttarakhand', 'Uttar Pradesh'],
        'South': ['Karnataka', 'Tamil Nadu', 'Kerala', 'Andhra Pradesh', 'Telangana'],
        'West': ['Maharashtra', 'Gujarat', 'Goa', 'Rajasthan'],
        'East': ['West Bengal', 'Odisha', 'Bihar', 'Jharkhand', 'Assam', 'Sikkim'],
        'Central': ['Madhya Pradesh', 'Chhattisgarh']
    }

    @classmethod
    def get_region_for_state(cls, state: str) -> str:
        if not state:
            return 'Central'
        for region, states in cls.REGIONS.items():
            if state in states:
                return region
        return 'Central'

    @classmethod
    def get_all_regions(cls) -> List[str]:
        return list(cls.REGIONS.keys())
