"""
Complete Journey Reconstruction and Fare Calculation System
Generates full journey details with all calculations for offline IRCTC simulation
"""
from datetime import datetime, date, timedelta, time
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass
import json
from sqlalchemy.orm import Session
from sqlalchemy import and_

from database.models import Stop, Trip, StopTime, Route, Calendar
from services.seat_allocation import CoachType


@dataclass
class SegmentDetail:
    """Complete details for one leg of journey"""
    segment_id: str              # Unique segment identifier
    train_number: str            # e.g., "12002"
    train_name: str              # e.g., "Rajdhani Express"
    depart_station: str          # Station name
    depart_code: str             # Station code
    depart_time: str             # HH:MM format
    depart_platform: str         # Platform number
    
    arrival_station: str         # Station name
    arrival_code: str            # Station code
    arrival_time: str            # HH:MM format
    arrival_platform: str        # Platform number
    
    distance_km: float           # Distance traveled
    travel_time_hours: float     # Duration in hours
    travel_time_mins: int        # Duration in minutes
    
    running_days: str            # "Mon, Tue, Wed, ..." or "Daily"
    halt_times: Dict[str, int]   # Station code -> halt minutes
    
    ac_first_available: int      # Seats available
    ac_second_available: int
    ac_third_available: int
    sleeper_available: int
    
    base_fare: float             # Base fare for segment
    tatkal_applicable: bool      # Tatkal special booking available
    
    def to_dict(self) -> Dict:
        return {
            "segment_id": self.segment_id,
            "train_number": self.train_number,
            "train_name": self.train_name,
            "departure": {
                "station": self.depart_station,
                "code": self.depart_code,
                "time": self.depart_time,
                "platform": self.depart_platform
            },
            "arrival": {
                "station": self.arrival_station,
                "code": self.arrival_code,
                "time": self.arrival_time,
                "platform": self.arrival_platform
            },
            "distance_km": self.distance_km,
            "travel_time": f"{int(self.travel_time_hours):02d}:{self.travel_time_mins % 60:02d}",
            "travel_time_minutes": self.travel_time_mins,
            "running_days": self.running_days,
            "halt_times": self.halt_times,
            "availability": {
                "ac_first": self.ac_first_available,
                "ac_second": self.ac_second_available,
                "ac_third": self.ac_third_available,
                "sleeper": self.sleeper_available
            },
            "fare": {
                "base_fare": self.base_fare,
                "currency": "INR",
                "tatkal_applicable": self.tatkal_applicable
            }
        }


@dataclass
class JourneyOption:
    """Complete journey with all segments"""
    journey_id: str              # Unique identifier
    segments: List[SegmentDetail]
    start_date: str              # YYYY-MM-DD
    end_date: str                # YYYY-MM-DD
    
    total_distance_km: float
    total_travel_time_mins: int
    num_segments: int
    num_transfers: int
    
    cheapest_fare: float         # Base fare for cheapest coach
    premium_fare: float          # Base fare for premium coach
    
    is_direct: bool              # True if single segment
    has_overnight: bool
    
    availability_status: str     # "available", "partially_available", "waitlist_only"
    
    def to_dict(self) -> Dict:
        return {
            "journey_id": self.journey_id,
            "num_segments": self.num_segments,
            "num_transfers": self.num_transfers,
            "is_direct": self.is_direct,
            "date": self.start_date,
            "distance_km": self.total_distance_km,
            "travel_time": f"{int(self.total_travel_time_mins // 60):02d}:{self.total_travel_time_mins % 60:02d}",
            "travel_time_minutes": self.total_travel_time_mins,
            "has_overnight": self.has_overnight,
            "fare": {
                "cheapest": self.cheapest_fare,
                "premium": self.premium_fare
            },
            "availability": self.availability_status,
            "segments": [seg.to_dict() for seg in self.segments]
        }


class FareCalculationEngine:
    """Calculate fares based on distance, coach type, concessions"""
    
    # Base fare per 100 km for each coach type (simplified IRCTC pattern)
    BASE_FARE_PER_100KM = {
        CoachType.AC_FIRST_CLASS: 350,
        CoachType.AC_TWO_TIER: 250,
        CoachType.AC_THREE_TIER: 150,
        CoachType.FIRST_CLASS: 120,
        CoachType.SLEEPER: 60,
        CoachType.GENERAL: 10,
        CoachType.SECOND_CLASS: 20,
    }
    
    # Surcharges
    SURCHARGES = {
        "extra_km_50_100": 1.1,      # 10% extra for 50-100km
        "extra_km_100_plus": 1.15,   # 15% extra for 100+ km
        "tatkal": 0.10,              # 10% tatkal charges
        "gst": 0.05,                 # 5% GST
    }
    
    # Concession discounts
    CONCESSION_DISCOUNTS = {
        "student": 0.25,             # 25% off
        "senior_citizen": 0.25,      # 25% off
        "military": 0.20,            # 20% off
        "disabled": 0.50,            # 50% off
        "freedom_fighter": 0.50,     # 50% off
    }
    
    def calculate_fare(
        self,
        distance_km: float,
        coach_type: CoachType,
        passenger_age: int = 30,
        concession_type: Optional[str] = None,
        is_tatkal: bool = False
    ) -> float:
        """Calculate complete fare for a segment
        
        Args:
            distance_km: Distance in km
            coach_type: Coach type
            passenger_age: Age of passenger
            concession_type: Concession code if applicable
            is_tatkal: Whether tatkal special booking
            
        Returns:
            Final fare in INR
        """
        # Base fare calculation
        base_per_100km = self.BASE_FARE_PER_100KM.get(coach_type, 100)
        base_fare = (distance_km / 100) * base_per_100km
        
        # Apply surcharge based on distance
        if 50 <= distance_km < 100:
            base_fare *= self.SURCHARGES["extra_km_50_100"]
        elif distance_km >= 100:
            base_fare *= self.SURCHARGES["extra_km_100_plus"]
        
        # Child discount (age 5-12)
        if 5 <= passenger_age < 12:
            base_fare *= 0.5
        
        # Senior citizen automatic discount (age 60+)
        elif passenger_age >= 60:
            base_fare *= 0.75
        
        # Apply concession discount
        if concession_type and concession_type in self.CONCESSION_DISCOUNTS:
            discount_rate = self.CONCESSION_DISCOUNTS[concession_type]
            base_fare *= (1 - discount_rate)
        
        # Add tatkal charges if applicable
        if is_tatkal:
            base_fare *= (1 + self.SURCHARGES["tatkal"])
        
        # Add GST
        base_fare *= (1 + self.SURCHARGES["gst"])
        
        return round(base_fare, 2)
    
    def calculate_return_fare(self, onward_fare: float) -> float:
        """Calculate return journey fare (typically 10% discount)"""
        return round(onward_fare * 0.9, 2)


class JourneyReconstructionEngine:
    """Complete journey reconstruction with all details"""
    
    def __init__(self, db: Session):
        self.db = db
        self.fare_engine = FareCalculationEngine()
        self._segment_counter = 0
    
    def reconstruct_single_segment_journey(
        self,
        trip_id: int,
        from_stop_id: int,
        to_stop_id: int,
        travel_date: date
    ) -> Optional[SegmentDetail]:
        """Reconstruct a single segment journey
        
        Args:
            trip_id: Trip ID
            from_stop_id: Starting stop ID
            to_stop_id: Ending stop ID
            travel_date: Travel date
            
        Returns:
            SegmentDetail or None if not found
        """
        # Get trip details
        trip = self.db.query(Trip).filter(Trip.id == trip_id).first()
        if not trip:
            return None
        
        # Get route details
        route = self.db.query(Route).filter(Route.id == trip.route_id).first()
        if not route:
            return None
        
        # Get calendar info
        calendar = self.db.query(Calendar).filter(Calendar.service_id == trip.service_id).first()
        
        # Get all stop times for this trip
        stop_times = self.db.query(StopTime).filter(
            StopTime.trip_id == trip_id
        ).order_by(StopTime.stop_sequence).all()
        
        if not stop_times or len(stop_times) < 2:
            return None
        
        # Find from_stop and to_stop in the sequence
        from_idx = None
        to_idx = None
        
        for idx, st in enumerate(stop_times):
            if st.stop_id == from_stop_id:
                from_idx = idx
            if st.stop_id == to_stop_id:
                to_idx = idx
        
        if from_idx is None or to_idx is None or from_idx >= to_idx:
            return None
        
        # Extract segment stop times
        from_st = stop_times[from_idx]
        to_st = stop_times[to_idx]
        
        # Get stops
        from_stop = self.db.query(Stop).filter(Stop.id == from_stop_id).first()
        to_stop = self.db.query(Stop).filter(Stop.id == to_stop_id).first()
        
        if not from_stop or not to_stop:
            return None
        
        # Calculate distance (simplified: use km from stop distance)
        distance_km = 50 + (to_idx - from_idx) * 150  # Rough estimate
        
        # Calculate travel time
        depart_time = from_st.departure_time
        arrival_time = to_st.arrival_time
        
        # Handle overnight journey
        if arrival_time < depart_time:
            # Next day arrival
            travel_time_obj = datetime.combine(
                datetime.today().date() + timedelta(days=1),
                arrival_time
            ) - datetime.combine(datetime.today().date(), depart_time)
        else:
            travel_time_obj = datetime.combine(
                datetime.today().date(),
                arrival_time
            ) - datetime.combine(datetime.today().date(), depart_time)
        
        travel_time_mins = int(travel_time_obj.total_seconds() / 60)
        travel_time_hours = travel_time_mins / 60
        
        # Extract halt times at intermediate stops
        halt_times = {}
        for idx in range(from_idx + 1, to_idx):
            st = stop_times[idx]
            stop = self.db.query(Stop).filter(Stop.id == st.stop_id).first()
            if stop:
                halt_mins = int((
                    datetime.combine(datetime.today(), st.departure_time) -
                    datetime.combine(datetime.today(), st.arrival_time)
                ).total_seconds() / 60)
                halt_times[stop.code or stop.name] = halt_mins
        
        # Get running days string
        running_days = self._get_running_days_string(calendar)
        
        # Simulate seat availability (all available initially in offline mode)
        seat_availability = {
            "ac_first": 18,
            "ac_second": 48,
            "ac_third": 64,
            "sleeper": 72
        }
        
        # Calculate base fare for strongest coach
        base_fare = self.fare_engine.calculate_fare(
            distance_km, CoachType.AC_THREE_TIER
        )
        
        # Check if tatkal is applicable (after 10 AM same day booking)
        is_tatkal = datetime.now().hour >= 10
        
        # Create segment
        self._segment_counter += 1
        segment = SegmentDetail(
            segment_id=f"SEG_{self._segment_counter:04d}",
            train_number=route.short_name or "TRAIN",
            train_name=route.long_name or "Express Train",
            depart_station=from_stop.name,
            depart_code=from_stop.code or from_stop.name[:3].upper(),
            depart_time=depart_time.strftime("%H:%M"),
            depart_platform=from_st.platform_number or "TBD",
            arrival_station=to_stop.name,
            arrival_code=to_stop.code or to_stop.name[:3].upper(),
            arrival_time=arrival_time.strftime("%H:%M"),
            arrival_platform=to_st.platform_number or "TBD",
            distance_km=round(distance_km, 2),
            travel_time_hours=travel_time_hours,
            travel_time_mins=travel_time_mins,
            running_days=running_days,
            halt_times=halt_times,
            ac_first_available=seat_availability["ac_first"],
            ac_second_available=seat_availability["ac_second"],
            ac_third_available=seat_availability["ac_third"],
            sleeper_available=seat_availability["sleeper"],
            base_fare=base_fare,
            tatkal_applicable=is_tatkal
        )
        
        return segment
    
    def reconstruct_complete_journey(
        self,
        segments: List[SegmentDetail],
        start_date: date
    ) -> JourneyOption:
        """Create complete journey from segments
        
        Args:
            segments: List of segment details
            start_date: Start date
            
        Returns:
            Complete JourneyOption
        """
        if not segments:
            raise ValueError("At least one segment required")
        
        # Calculate totals
        total_distance = sum(s.distance_km for s in segments)
        total_travel_time = sum(s.travel_time_mins for s in segments)
        num_transfers = len(segments) - 1
        
        # Determine if overnight
        has_overnight = False
        if len(segments) > 1:
            for i, seg in enumerate(segments[:-1]):
                next_seg = segments[i + 1]
                # If arrival time > departure time of next segment, it's not same day
                if seg.arrival_time > next_seg.depart_time:
                    has_overnight = True
                    break
        
        # Calculate end date based on overnight status
        if has_overnight:
            end_date = start_date + timedelta(days=1)
        else:
            end_date = start_date
        
        # Get fare range
        cheapest_fare = min(s.base_fare for s in segments)
        premium_fare = max(s.base_fare for s in segments) * 1.5  # Estimate
        
        # Determine availability status
        all_available = all(s.ac_third_available > 0 for s in segments)
        some_available = any(s.ac_third_available > 0 for s in segments)
        
        if all_available:
            availability_status = "available"
        elif some_available:
            availability_status = "partially_available"
        else:
            availability_status = "waitlist_only"
        
        # Create journey
        journey = JourneyOption(
            journey_id=f"JRN_{int(datetime.now().timestamp() * 1000) % 1000000:06d}",
            segments=segments,
            start_date=start_date.isoformat(),
            end_date=end_date.isoformat(),
            total_distance_km=round(total_distance, 2),
            total_travel_time_mins=total_travel_time,
            num_segments=len(segments),
            num_transfers=num_transfers,
            cheapest_fare=round(cheapest_fare, 2),
            premium_fare=round(premium_fare, 2),
            is_direct=len(segments) == 1,
            has_overnight=has_overnight,
            availability_status=availability_status
        )
        
        return journey
    
    def _get_running_days_string(self, calendar: Optional[Calendar]) -> str:
        """Convert calendar record to readable running days"""
        if not calendar:
            return "Daily"
        
        days = []
        day_map = [
            ("Monday", calendar.monday),
            ("Tuesday", calendar.tuesday),
            ("Wednesday", calendar.wednesday),
            ("Thursday", calendar.thursday),
            ("Friday", calendar.friday),
            ("Saturday", calendar.saturday),
            ("Sunday", calendar.sunday),
        ]
        
        for day_name, is_running in day_map:
            if is_running:
                days.append(day_name[:3])
        
        if len(days) == 7:
            return "Daily"
        elif len(days) == 5 and "Sat" not in days and "Sun" not in days:
            return "Weekdays"
        elif len(days) == 2 and "Sat" in days and "Sun" in days:
            return "Weekends"
        else:
            return ", ".join(days)
