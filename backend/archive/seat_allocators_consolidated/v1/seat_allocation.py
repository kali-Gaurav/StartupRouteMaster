"""
Seat Allocation System - Complete implementation for offline testing
Handles seat availability, allocation, blocking, and confirmation
"""
from datetime import datetime, date, timedelta
from enum import Enum
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass, field
from sqlalchemy.orm import Session
from sqlalchemy import and_, or_
import json

from backend.models import Trip, Stop, StopTime, Booking, PassengerDetails, Disruption
from backend.utils.generators import generate_pnr


class CoachType(str, Enum):
    """Coach/compartment types in Indian railways"""
    AC_FIRST_CLASS = "1A"      # AC First Class - 18 seats
    AC_TWO_TIER = "2A"         # AC 2-Tier - 48 seats
    AC_THREE_TIER = "3A"       # AC 3-Tier - 64 seats
    FIRST_CLASS = "FC"         # First Class - 48 seats
    SLEEPER = "SL"             # Sleeper - 72 seats
    GENERAL = "GN"             # General/Unreserved - 200 seats
    SECOND_CLASS = "2S"        # Second Class - 120 seats


class SeatType(str, Enum):
    """Seat types within coach"""
    LOWER = "LOWER"
    MIDDLE = "MIDDLE"
    UPPER = "UPPER"
    SIDE_LOWER = "SIDE_L"
    SIDE_UPPER = "SIDE_U"
    WINDOW = "WINDOW"
    AISLE = "AISLE"


class SeatStatus(str, Enum):
    """Status of seat"""
    AVAILABLE = "available"
    BOOKED = "booked"
    BLOCKED = "blocked"          # Blocked for maintenance
    RESERVED = "reserved"        # Reserved for differently-abled
    WAITING_LIST = "waiting"     # On waiting list


@dataclass
class Seat:
    """Represents a single seat"""
    seat_id: str                 # Coach_Seat_Type (e.g., A_01_LOWER)
    coach_number: str            # A, B, C, D, etc
    seat_number: int             # 1-72
    seat_type: SeatType          # Lower, Middle, Upper, etc
    status: SeatStatus = SeatStatus.AVAILABLE
    booked_by_pnr: Optional[str] = None
    booked_at: Optional[datetime] = None
    passenger_name: Optional[str] = None
    passenger_age: Optional[int] = None
    concession: Optional[str] = None
    
    def to_dict(self) -> Dict:
        return {
            "seat_id": self.seat_id,
            "coach": self.coach_number,
            "seat_number": self.seat_number,
            "seat_type": self.seat_type.value,
            "status": self.status.value,
            "booked_by": self.booked_by_pnr,
            "passenger_name": self.passenger_name,
            "passenger_age": self.passenger_age,
            "concession": self.concession
        }


@dataclass
class Coach:
    """Represents a coach/compartment"""
    coach_id: str               # A, B, C, etc (0-based index)
    coach_type: CoachType       # 2A, 3A, SL, etc
    total_seats: int
    seats: Dict[str, Seat] = field(default_factory=dict)
    
    def initialize_seats(self):
        """Initialize seats based on coach type"""
        seat_configs = {
            CoachType.AC_FIRST_CLASS: 18,
            CoachType.AC_TWO_TIER: 48,
            CoachType.AC_THREE_TIER: 64,
            CoachType.FIRST_CLASS: 48,
            CoachType.SLEEPER: 72,
            CoachType.GENERAL: 200,
            CoachType.SECOND_CLASS: 120,
        }
        
        total = seat_configs.get(self.coach_type, 48)
        self.total_seats = total
        
        # Create seats based on coach type
        seat_types_config = {
            CoachType.AC_FIRST_CLASS: [SeatType.LOWER, SeatType.UPPER],
            CoachType.AC_TWO_TIER: [SeatType.LOWER, SeatType.MIDDLE, SeatType.UPPER],
            CoachType.AC_THREE_TIER: [SeatType.LOWER, SeatType.MIDDLE, SeatType.UPPER],
            CoachType.SLEEPER: [SeatType.LOWER, SeatType.MIDDLE, SeatType.UPPER, SeatType.SIDE_LOWER, SeatType.SIDE_UPPER],
            CoachType.GENERAL: [SeatType.WINDOW, SeatType.AISLE],
        }
        
        seat_types = seat_types_config.get(self.coach_type, [SeatType.LOWER, SeatType.UPPER])
        
        seat_counter = 0
        for i in range(1, total + 1):
            # Rotate through seat types
            seat_type = seat_types[seat_counter % len(seat_types)]
            seat_counter += 1
            
            seat_id = f"{self.coach_id}_{i:02d}_{seat_type.value}"
            self.seats[seat_id] = Seat(
                seat_id=seat_id,
                coach_number=self.coach_id,
                seat_number=i,
                seat_type=seat_type
            )
    
    def get_available_seats(self, count: int = 1) -> List[Seat]:
        """Get available seats, preferring lower berths, then middle, then upper"""
        preference_order = [
            SeatType.LOWER, SeatType.SIDE_LOWER,
            SeatType.MIDDLE,
            SeatType.UPPER, SeatType.SIDE_UPPER,
            SeatType.WINDOW, SeatType.AISLE
        ]
        
        available = []
        for pref_type in preference_order:
            for seat in self.seats.values():
                if seat.status == SeatStatus.AVAILABLE and seat.seat_type == pref_type:
                    available.append(seat)
                    if len(available) == count:
                        return available
        
        return available


@dataclass
class TrainCompartment:
    """Represents complete train with all coaches"""
    trip_id: str
    coaches: Dict[str, Coach] = field(default_factory=dict)
    
    def initialize_train(self, coach_types: List[Tuple[str, CoachType]]):
        """Initialize train with specified coaches
        
        Args:
            coach_types: List of (coach_id, CoachType) tuples
                Example: [("A", CoachType.AC_TWO_TIER), ("B", CoachType.AC_THREE_TIER)]
        """
        for coach_id, coach_type in coach_types:
            coach = Coach(coach_id=coach_id, coach_type=coach_type, total_seats=0)
            coach.initialize_seats()
            self.coaches[coach_id] = coach
    
    def get_available_seats_all_coaches(self, count: int = 1) -> List[Seat]:
        """Get available seats across all coaches"""
        available = []
        for coach in self.coaches.values():
            available.extend(coach.get_available_seats(count - len(available)))
            if len(available) >= count:
                break
        return available[:count]
    
    def allocate_seats(
        self, 
        passengers: List[Dict],
        coach_preference: CoachType = CoachType.AC_THREE_TIER
    ) -> Dict:
        """Allocate seats for passengers
        
        Args:
            passengers: List of passenger dicts with name, age, gender, concession
            coach_preference: Preferred coach type
            
        Returns:
            Dict with allocated seats and any waiting list
        """
        allocated = []
        waiting_list = []
        
        for passenger in passengers:
            # Try to allocate from preferred coach first
            pref_coach = [c for c in self.coaches.values() if c.coach_type == coach_preference]
            
            seat_found = False
            for coach in pref_coach:
                available = coach.get_available_seats(1)
                if available:
                    seat = available[0]
                    seat.status = SeatStatus.BOOKED
                    seat.passenger_name = passenger.get("full_name", "Unknown")
                    seat.passenger_age = passenger.get("age")
                    seat.concession = passenger.get("concession_type")
                    allocated.append({
                        "passenger": passenger.get("full_name"),
                        "seat": seat.to_dict(),
                        "coach": coach.coach_id,
                        "fare_applicable": self._calculate_seat_fare(
                            seat, passenger.get("age"), passenger.get("concession_type")
                        )
                    })
                    seat_found = True
                    break
            
            if not seat_found:
                # No seat in preferred coach, try any coach
                seats = self.get_available_seats_all_coaches(1)
                if seats:
                    seat = seats[0]
                    seat.status = SeatStatus.BOOKED
                    seat.passenger_name = passenger.get("full_name")
                    seat.passenger_age = passenger.get("age")
                    seat.concession = passenger.get("concession_type")
                    allocated.append({
                        "passenger": passenger.get("full_name"),
                        "seat": seat.to_dict(),
                        "coach": seat.coach_number,
                        "fare_applicable": self._calculate_seat_fare(
                            seat, passenger.get("age"), passenger.get("concession_type")
                        )
                    })
                else:
                    # No seat available - waiting list
                    waiting_list.append({
                        "passenger": passenger.get("full_name"),
                        "age": passenger.get("age"),
                        "position": len(waiting_list) + 1
                    })
        
        return {
            "allocated_seats": allocated,
            "waiting_list": waiting_list,
            "total_allocated": len(allocated),
            "total_waiting": len(waiting_list)
        }
    
    def _calculate_seat_fare(self, seat: Seat, age: int, concession: Optional[str]) -> float:
        """Calculate fare for seat based on type and concessions"""
        base_fare = {
            CoachType.AC_FIRST_CLASS: 3500,
            CoachType.AC_TWO_TIER: 2500,
            CoachType.AC_THREE_TIER: 1500,
            CoachType.FIRST_CLASS: 1200,
            CoachType.SLEEPER: 600,
            CoachType.GENERAL: 100,
            CoachType.SECOND_CLASS: 200,
        }
        
        # Get coach info from seats
        for coach in self.coaches.values():
            if seat.seat_id in coach.seats:
                fare = base_fare.get(coach.coach_type, 500)
                break
        else:
            fare = 500
        
        # Child discount (age 5-12)
        if 5 <= age < 12:
            fare *= 0.5
        
        # Senior citizen discount (60+)
        elif age >= 60:
            fare *= 0.75
        
        # Apply concession discount if applicable
        concession_discounts = {
            "student": 0.25,
            "military": 0.20,
            "disabled": 0.50,
            "senior_citizen": 0.25
        }
        
        if concession and concession in concession_discounts:
            discount_rate = concession_discounts[concession]
            fare *= (1 - discount_rate)
        
        return round(fare, 2)
    
    def release_seats(self, pnr_number: str):
        """Release seats for a cancelled booking"""
        for coach in self.coaches.values():
            for seat in coach.seats.values():
                if seat.booked_by_pnr == pnr_number:
                    seat.status = SeatStatus.AVAILABLE
                    seat.booked_by_pnr = None
                    seat.passenger_name = None
                    seat.passenger_age = None
    
    def get_seat_availability_percentage(self) -> Dict[str, float]:
        """Get seat availability percentage per coach"""
        availability = {}
        for coach_id, coach in self.coaches.items():
            available_count = sum(1 for s in coach.seats.values() if s.status == SeatStatus.AVAILABLE)
            percentage = (available_count / coach.total_seats * 100) if coach.total_seats > 0 else 0
            availability[coach_id] = {
                "coach_type": coach.coach_type.value,
                "available": available_count,
                "total": coach.total_seats,
                "percentage": round(percentage, 2)
            }
        return availability
    
    def to_dict(self) -> Dict:
        """Serialize train state"""
        return {
            "trip_id": self.trip_id,
            "coaches": {
                coach_id: {
                    "coach_type": coach.coach_type.value,
                    "total_seats": coach.total_seats,
                    "available": sum(1 for s in coach.seats.values() if s.status == SeatStatus.AVAILABLE),
                    "booked": sum(1 for s in coach.seats.values() if s.status == SeatStatus.BOOKED),
                }
                for coach_id, coach in self.coaches.items()
            },
            "availability": self.get_seat_availability_percentage()
        }


class SeatAllocationService:
    """Service to manage seat allocation for bookings"""
    
    def __init__(self, db: Session):
        self.db = db
        self.trains: Dict[str, TrainCompartment] = {}  # trip_id -> TrainCompartment
    
    def initialize_train_for_trip(self, trip_id: str, coach_layout: List[Tuple[str, CoachType]]):
        """Initialize train for a specific trip
        
        Args:
            trip_id: Trip ID
            coach_layout: List of (coach_id, CoachType) tuples
        """
        train = TrainCompartment(trip_id=trip_id)
        train.initialize_train(coach_layout)
        self.trains[trip_id] = train
    
    def allocate_seats_for_booking(
        self,
        trip_id: str,
        passengers: List[Dict],
        coach_preference: CoachType = CoachType.AC_THREE_TIER
    ) -> Dict:
        """Allocate seats for a booking
        
        Returns:
            {
                "success": bool,
                "allocated_seats": List[seat_info],
                "waiting_list": List[passenger_info],
                "total_fare": float,
                "seat_details": str (for booking confirmation)
            }
        """
        if trip_id not in self.trains:
            # Auto-initialize with standard Rajdhani Express layout
            self.initialize_train_for_trip(
                trip_id,
                [
                    ("A", CoachType.AC_FIRST_CLASS),
                    ("B", CoachType.AC_TWO_TIER),
                    ("C", CoachType.AC_TWO_TIER),
                    ("D", CoachType.AC_THREE_TIER),
                    ("E", CoachType.AC_THREE_TIER),
                    ("F", CoachType.SLEEPER),
                    ("G", CoachType.SLEEPER),
                    ("H", CoachType.GENERAL),
                ]
            )
        
        train = self.trains[trip_id]
        allocation = train.allocate_seats(passengers, coach_preference)
        
        # Calculate total fare
        total_fare = sum(s.get("fare_applicable", 0) for s in allocation["allocated_seats"])
        
        # Create readable seat details string
        seat_details = self._format_seat_details(allocation)
        
        return {
            "success": len(allocation["allocated_seats"]) > 0,
            "allocated_seats": allocation["allocated_seats"],
            "waiting_list": allocation["waiting_list"],
            "total_fare": total_fare,
            "seat_details": seat_details,
            "summary": {
                "total_allocated": allocation["total_allocated"],
                "total_waiting": allocation["total_waiting"],
                "total_passengers": len(passengers)
            }
        }
    
    def _format_seat_details(self, allocation: Dict) -> str:
        """Format seat allocation for display"""
        details = []
        for seated in allocation["allocated_seats"]:
            seat_info = seated["seat"]
            details.append(
                f"• {seated['passenger']}: Coach {seated['coach']}, "
                f"Seat {seat_info['seat_number']} ({seat_info['seat_type']}) - "
                f"₹{seated.get('fare_applicable', 0)}"
            )
        
        if allocation["waiting_list"]:
            details.append("\n⏳ WAITING LIST:")
            for wl in allocation["waiting_list"]:
                details.append(f"• {wl['passenger']}: WL #{wl['position']}")
        
        return "\n".join(details)
    
    def block_seats(self, trip_id: str, seat_ids: List[str]) -> bool:
        """Block seats for maintenance/reservation"""
        if trip_id not in self.trains:
            return False
        
        train = self.trains[trip_id]
        for seat_id in seat_ids:
            for coach in train.coaches.values():
                if seat_id in coach.seats:
                    coach.seats[seat_id].status = SeatStatus.BLOCKED
                    break
        return True
    
    def get_train_occupancy(self, trip_id: str) -> Dict:
        """Get occupancy details for a train"""
        if trip_id not in self.trains:
            return {}
        
        train = self.trains[trip_id]
        return {
            "trip_id": trip_id,
            "coaches": train.to_dict()["coaches"],
            "availability": train.get_seat_availability_percentage()
        }
