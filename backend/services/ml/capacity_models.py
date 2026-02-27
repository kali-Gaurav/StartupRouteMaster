"""
Capacity Prediction Models for RouteMaster V2.
Predicts seat availability probability and occupancy trends.
"""

import logging
import numpy as np
import pandas as pd
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from sqlalchemy.orm import Session
from sqlalchemy import desc, func

from database.models import SeatAvailability, TrainMaster

logger = logging.getLogger(__name__)

class CapacityPredictionModel:
    """
    Predicts the probability of a seat being available for a given train/date/class.
    Uses historical availability logs (The Moat Dataset).
    """
    
    def __init__(self):
        self.is_trained = False
        # Placeholder for actual model (XGBoost/RandomForest)
        self.model = None 

    def predict_availability_probability(self, session: Session, train_number: str, 
                                        class_code: str, travel_date: datetime, 
                                        quota: str = "GN") -> float:
        """
        Returns P(Available) - probability from 0.0 to 1.0.
        
        Logic for 0-Data Start:
        1. If no historical data, return a baseline based on train type.
        2. If historical data exists, use trend analysis.
        """
        try:
            # Normalize travel_date to date for database consistency
            if isinstance(travel_date, datetime):
                travel_date_norm = travel_date.date()
            else:
                travel_date_norm = travel_date

            # 1. Fetch recent history for this specific combination
            history = session.query(SeatAvailability).filter(
                SeatAvailability.train_number == train_number,
                SeatAvailability.class_code == class_code,
                SeatAvailability.quota == quota,
                func.date(SeatAvailability.travel_date) == travel_date_norm
            ).order_by(desc(SeatAvailability.check_date)).limit(10).all()
            
            if not history:
                return self._get_baseline_probability(session, train_number, class_code)
                
            # 2. Simple Heuristic if model not yet trained:
            # Check latest status
            latest = history[0]
            status = latest.availability_status.upper()
            
            if "AVAILABLE" in status or "CURR_AVBL" in status:
                # If available now, probability is high but decays as travel_date nears
                days_left = (travel_date - datetime.utcnow()).days
                return max(0.6, 1.0 - (0.01 * (30 - max(0, days_left))))
                
            if "WL" in status:
                # If in Waiting List, probability depends on WL number
                wl_num = latest.waiting_list_number or 100
                if wl_num < 10: return 0.5
                if wl_num < 50: return 0.2
                return 0.05
                
            return 0.5 # Default neutral
            
        except Exception as e:
            logger.error(f"Error predicting availability for {train_number}: {e}")
            return 0.5

    def _get_baseline_probability(self, session: Session, train_number: str, class_code: str) -> float:
        """Baseline P(avail) based on train frequency and type."""
        train = session.query(TrainMaster).filter(TrainMaster.train_number == train_number).first()
        if not train: return 0.5
        
        # Express trains usually have lower availability than local/fast passengers
        if "Express" in (train.type or ""):
            return 0.4 if class_code in ["3A", "SL"] else 0.6
        return 0.7

    def get_occupancy_penalty(self, probability: float) -> float:
        """
        Calculates a penalty score for the routing engine.
        Low probability (high occupancy) -> High penalty.
        """
        # Penalty = (1 - P)^2 * 100 
        # Example: P=1.0 -> 0 penalty. P=0.0 -> 100 penalty.
        return round(((1.0 - probability) ** 2) * 100, 2)
