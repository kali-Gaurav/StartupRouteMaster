"""
Seat Allocation System - UNIFIED PRODUCTION VERSION
Uses database models instead of in-memory simulations
"""
from datetime import datetime, date, timedelta
from enum import Enum
from typing import List, Dict, Optional, Tuple, Any
from sqlalchemy.orm import Session
from sqlalchemy import and_
import logging

from database.models import SeatInventory

logger = logging.getLogger(__name__)

class CoachType(str, Enum):
    AC_FIRST_CLASS = "AC_1"
    AC_TWO_TIER = "AC_2"
    AC_THREE_TIER = "AC_3"
    SLEEPER = "SL"
    GENERAL = "GN"

class SeatAllocationService:
    def __init__(self, db: Session):
        self.db = db

    def allocate_seats_for_booking(
        self,
        trip_id: str,
        passengers: List[Dict],
        coach_preference: str = "AC_THREE_TIER",
        travel_date: date = None
    ) -> Dict:
        """
        Allocate seats by querying SeatInventory in database.
        """
        if not travel_date:
            travel_date = date.today()

        # UNIFIED LOGIC: Find inventory in database
        inventory = self.db.query(SeatInventory).filter(
            SeatInventory.stop_time_id == int(trip_id), # Simplified
            SeatInventory.travel_date == travel_date,
            SeatInventory.coach_type == coach_preference
        ).first()

        # Fallback for "Rich Database" development: If missing, auto-populate
        if not inventory:
            logger.info("Auto-populating SeatInventory for trip %s", trip_id)
            inventory = SeatInventory(
                travel_date=travel_date,
                coach_type=coach_preference,
                seats_available=64,
                stop_time_id=int(trip_id)
            )
            self.db.add(inventory)
            self.db.commit()
            self.db.refresh(inventory)

        count = len(passengers)
        success = inventory.seats_available >= count

        allocated_seats = []
        waiting_list = []

        if success:
            inventory.seats_available -= count
            self.db.commit()
            
            for i, p in enumerate(passengers):
                allocated_seats.append({
                    "passenger": p.get("full_name"),
                    "coach": f"{coach_preference[:2]}-1",
                    "seat": {"seat_number": 64 - inventory.seats_available - i, "seat_type": "LOWER"},
                    "fare_applicable": 1500.0
                })
        else:
            waiting_list = [{"passenger": p.get("full_name"), "position": i+1} for i, p in enumerate(passengers)]

        return {
            "success": success,
            "allocated_seats": allocated_seats,
            "waiting_list": waiting_list,
            "total_fare": sum(s["fare_applicable"] for s in allocated_seats),
            "seat_details": f"Allocated {len(allocated_seats)} seats in {coach_preference}"
        }
