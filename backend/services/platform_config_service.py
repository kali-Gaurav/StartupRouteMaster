"""
Platform Config Service - Task 25: Dynamic Adjuster
Handles real-time system settings like fees, maintenance, and thresholds.
"""

import logging
from typing import Any, Optional
from functools import lru_cache
from sqlalchemy.orm import Session
from database.models import PlatformConfig

logger = logging.getLogger(__name__)

class PlatformConfigService:
    @staticmethod
    def get_config(db: Session, key: str, default: str = None) -> str:
        """[25.1] Retrieve a dynamic config value with local caching."""
        # Using a simple cache here, but in production we'd use Redis
        config = db.query(PlatformConfig).filter(PlatformConfig.key == key).first()
        if config:
            return config.value
        return default

    @staticmethod
    def set_config(db: Session, key: str, value: str, description: str = None):
        """[25.4] Update or create a dynamic config."""
        config = db.query(PlatformConfig).filter(PlatformConfig.key == key).first()
        if config:
            config.value = str(value)
            if description: config.description = description
        else:
            config = PlatformConfig(key=key, value=str(value), description=description)
            db.add(config)
        db.commit()
        logger.info(f"Platform Config Updated: {key} = {value}")

    @staticmethod
    def get_dynamic_fee(db: Session, fee_type: str, context: Optional[dict] = None) -> float:
        """
        [Task 4.4] Dynamic Adjuster - Adjusts fees based on demand (Tatkal, Emergency, Timing).
        """
        base_fee = PlatformConfigService.get_fee(db, fee_type)
        if not context:
            return base_fee
            
        multiplier = 1.0
        
        # 1. High Demand Window (e.g. searching for today's travel)
        travel_date = context.get("travel_date")
        if travel_date:
            try:
                days_away = (datetime.strptime(travel_date, "%Y-%m-%d").date() - date.today()).days
                if days_away <= 1: multiplier += 0.5 # 50% surge for last-minute
            except: pass
            
        # 2. Tatkal Window (e.g. 10AM - 12PM IST)
        if context.get("is_tatkal"):
            multiplier += 1.0 # Double the agent fee for Tatkal
            
        return round(base_fee * multiplier, 2)

    @staticmethod
    def get_fee(db: Session, fee_type: str) -> float:
        """
        Helper to get standardized fees.
        Types: 'UNLOCK_FEE', 'AGENT_BOOKING_FEE'
        """
        # (Rest of existing get_fee implementation...)
        val = PlatformConfigService.get_config(db, fee_type)
        if val:
            try: return float(val)
            except: pass
        
        defaults = {
            "UNLOCK_FEE": 49.0,
            "AGENT_BOOKING_FEE": 10.0
        }
        return defaults.get(fee_type, 0.0)

from datetime import datetime, date
