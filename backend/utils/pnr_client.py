from typing import Dict, Any, Optional
import random

class PNRClient:
    """
    Client for fetching live PNR status.
    In a real app, this connects to a 3rd party API.
    """
    
    @staticmethod
    async def get_status(pnr: str) -> Optional[Dict[str, Any]]:
        """
        Returns mock status for the 10-digit PNR.
        """
        if not pnr or len(pnr) != 10:
            return None
            
        # Mock Data Generation
        return {
            "pnr": pnr,
            "train_number": "12628",
            "train_name": "KARNATAKA EXP",
            "date": "2026-03-10",
            "from": "NDLS",
            "to": "SBC",
            "passengers": [
                {"no": 1, "status": "CNF", "coach": "B2", "seat": "24", "berth": "UB"},
                {"no": 2, "status": "CNF", "coach": "B2", "seat": "25", "berth": "LB"}
            ],
            "delay_minutes": random.choice([0, 15, 45, 120]),
            "platform": random.choice(["1", "3", "8"])
        }
