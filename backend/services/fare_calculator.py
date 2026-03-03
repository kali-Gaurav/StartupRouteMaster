import logging
from typing import Optional, Dict
from sqlalchemy.orm import Session
from database.models import Fare
from sqlalchemy import and_

logger = logging.getLogger(__name__)

class FareCalculator:
    """
    Service to calculate or look up fares for train segments.
    Uses a hybrid approach:
    1. Database lookup for exact segment/train/class matches.
    2. Fallback to a distance-based linear regression model (Base Fare + Rate/KM).
    """

    # IRCTC-aligned rates (approximate INR per KM)
    CLASS_RATES = {
        "1A": 4.5,
        "2A": 2.5,
        "3A": 1.8,
        "3E": 1.6,
        "SL": 0.7,
        "2S": 0.4,
        "CC": 2.0,
        "EC": 3.5,
        "FC": 2.8,
        "GN": 0.2
    }

    # Base fare (minimum) per class
    BASE_FARES = {
        "1A": 500,
        "2A": 300,
        "3A": 250,
        "3E": 200,
        "SL": 120,
        "2S": 60,
        "CC": 200,
        "EC": 400,
        "FC": 200,
        "GN": 30
    }

    @classmethod
    def calculate_fare(
        self, 
        db: Session, 
        distance_km: float, 
        class_type: str = "SL", 
        train_no: Optional[str] = None,
        segment_id: Optional[str] = None
    ) -> float:
        """Calculate the best estimate for a fare."""
        class_type = class_type.upper()
        
        # 1. Try DB Lookup
        try:
            db_fare = db.query(Fare).filter(and_(
                Fare.class_type == class_type,
                (Fare.segment_id == segment_id) if segment_id else (Fare.id == -1) # dummy if no segment_id
            )).first()
            if db_fare:
                return float(db_fare.amount)
        except Exception as e:
            logger.debug(f"Fare DB lookup failed: {e}")

        # 2. Fallback to Linear Model
        rate = self.CLASS_RATES.get(class_type, self.CLASS_RATES["SL"])
        base = self.BASE_FARES.get(class_type, self.BASE_FARES["SL"])
        
        estimated = base + (distance_km * rate)
        
        # Round to nearest 5 as per IRCTC convention
        return float(round(estimated / 5) * 5)

    @classmethod
    def get_all_fares(self, db: Session, distance_km: float) -> Dict[str, float]:
        """Get estimated fares for all available classes."""
        return {
            cls: self.calculate_fare(db, distance_km, cls)
            for cls in self.CLASS_RATES.keys()
        }
