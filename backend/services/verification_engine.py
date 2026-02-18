"""
Verification & Unlock Details System
Simulates real-time verification checks when user clicks on journey details
"""
from datetime import datetime, date, timedelta
from typing import Dict, List, Optional, Tuple
from enum import Enum
from dataclasses import dataclass, asdict
import json

from backend.services.journey_reconstruction import JourneyOption, SegmentDetail


class VerificationStatus(str, Enum):
    """Status of verification check"""
    VERIFIED = "verified"
    PENDING = "pending"
    FAILED = "failed"
    DELAYED = "delayed"
    CANCELLED = "cancelled"


@dataclass
class SeatCheckResult:
    """Result of seat availability check"""
    status: VerificationStatus
    total_seats: int
    available_seats: int
    booked_seats: int
    waiting_list_position: Optional[int] = None
    message: str = ""


@dataclass
class TrainScheduleCheckResult:
    """Result of train schedule verification"""
    status: VerificationStatus
    scheduled_departure: str      # HH:MM
    scheduled_arrival: str        # HH:MM
    actual_departure: Optional[str] = None
    actual_arrival: Optional[str] = None
    delay_minutes: int = 0
    message: str = ""


@dataclass
class FareCheckResult:
    """Result of fare verification"""
    status: VerificationStatus
    base_fare: float
    GST: float
    total_fare: float
    applicable_discounts: List[str] = None
    cancellation_charges: float = 0.0
    message: str = ""


@dataclass
class VerificationDetails:
    """Complete verification result for a journey"""
    journey_id: str
    verification_timestamp: str
    overall_status: VerificationStatus
    
    seat_verification: SeatCheckResult
    schedule_verification: TrainScheduleCheckResult
    fare_verification: FareCheckResult
    
    restrictions: List[str]        # Any restrictions on booking
    warnings: List[str]           # Warnings to show user
    
    is_bookable: bool             # Can user proceed to booking


class SimulatedRealTimeDataProvider:
    """Simulates real-time data checks for offline testing
    
    In production, this would connect to actual IRCTC APIs and live data sources.
    For now, it simulates various scenarios based on time, date, and availability.
    """
    
    def __init__(self):
        self.booking_window = 60  # Days in advance bookable
        self.tatkal_booking_time = 10.0  # 10 AM same-day tatkal
        
        # Simulation: Some trains delayed, some cancelled on specific dates
        self.simulated_delays = {}  # journey_id -> delay_minutes
        self.simulated_cancellations = {}  # journey_id -> cancellation_reason
    
    def verify_seat_availability(
        self,
        segment: SegmentDetail,
        journey_date: date,
        coach_preference: str = "AC_THREE_TIER"
    ) -> SeatCheckResult:
        """Simulate seat availability check
        
        In offline mode:
        - Initial dataset has all seats available
        - Gradually fill seats as more bookings are made
        - Simulate waiting list only after 90% capacity
        """
        
        # Use segment availability data
        available_map = {
            "AC_FIRST": segment.ac_first_available,
            "AC_TWO": 0,  # Not used
            "AC_THREE_TIER": segment.ac_third_available,
            "SLEEPER": segment.sleeper_available,
        }
        
        total_seats = getattr(segment, f"{coach_preference}_available", 64)
        available = available_map.get(coach_preference, 64)
        booked = 64 - available  # Estimate
        
        if total_seats <= 0:
            return SeatCheckResult(
                status=VerificationStatus.VERIFIED,
                total_seats=0,
                available_seats=0,
                booked_seats=0,
                waiting_list_position=1,
                message="Only waiting list available"
            )
        
        availability_percentage = (available / total_seats) * 100
        
        if availability_percentage > 50:
            status = VerificationStatus.VERIFIED
            message = "Seats available"
        elif availability_percentage > 10:
            status = VerificationStatus.VERIFIED
            message = "Few seats available"
        elif availability_percentage > 0:
            status = VerificationStatus.VERIFIED
            message = "Last few seats available - Book now!"
        else:
            status = VerificationStatus.VERIFIED
            message = "Waiting list available"
        
        return SeatCheckResult(
            status=status,
            total_seats=total_seats,
            available_seats=int(available),
            booked_seats=int(booked),
            waiting_list_position=None if available > 0 else 1,
            message=message
        )
    
    def verify_train_schedule(
        self,
        segment: SegmentDetail,
        journey_date: date
    ) -> TrainScheduleCheckResult:
        """Simulate train schedule verification
        
        In offline mode:
        - Use GTFS data from database
        - Simulate occasional delays (10% chance)
        - Simulate occasional cancellations (2% chance)
        """
        
        scheduled_departure = segment.depart_time
        scheduled_arrival = segment.arrival_time
        
        # Check if train is in simulated delays/cancellations
        journey_key = f"{segment.train_number}_{journey_date.isoformat()}"
        
        if journey_key in self.simulated_cancellations:
            return TrainScheduleCheckResult(
                status=VerificationStatus.CANCELLED,
                scheduled_departure=scheduled_departure,
                scheduled_arrival=scheduled_arrival,
                message=self.simulated_cancellations[journey_key]
            )
        
        delay_minutes = self.simulated_delays.get(journey_key, 0)
        
        if delay_minutes > 0:
            # Calculate actual times with delay
            from datetime import datetime, time
            
            time_obj = datetime.strptime(scheduled_departure, "%H:%M")
            time_obj += timedelta(minutes=delay_minutes)
            actual_departure = time_obj.time().strftime("%H:%M")
            
            time_obj = datetime.strptime(scheduled_arrival, "%H:%M")
            time_obj += timedelta(minutes=delay_minutes)
            actual_arrival = time_obj.time().strftime("%H:%M")
            
            status = VerificationStatus.DELAYED
            message = f"Train running {delay_minutes} minutes late (simulation)"
        else:
            actual_departure = scheduled_departure
            actual_arrival = scheduled_arrival
            status = VerificationStatus.VERIFIED
            message = "Train on schedule"
        
        return TrainScheduleCheckResult(
            status=status,
            scheduled_departure=scheduled_departure,
            scheduled_arrival=scheduled_arrival,
            actual_departure=actual_departure,
            actual_arrival=actual_arrival,
            delay_minutes=delay_minutes,
            message=message
        )
    
    def verify_fare(
        self,
        segment: SegmentDetail,
        journey_date: date,
        passenger_age: int = 30,
        concession_type: Optional[str] = None
    ) -> FareCheckResult:
        """Simulate fare verification and dynamic pricing
        
        In offline mode:
        - Use base fares from GTFS cost field
        - Apply standard discounts (children, seniors, concessions)
        - Add GST (5%)
        - Simulate dynamic pricing near travel date (higher fares closer to date)
        """
        
        days_until_travel = (journey_date - date.today()).days
        
        base_fare = segment.base_fare
        
        # Dynamic pricing: Increase fare if booking within 7 days
        if 0 < days_until_travel <= 7:
            surge_multiplier = 1 + (0.10 * (7 - days_until_travel) / 7)  # Up to 10% surge
            base_fare *= surge_multiplier
        elif days_until_travel <= 0:
            # Same day or past booking - only tatkal available
            base_fare *= 1.20
        
        # Apply age-based discounts
        if 5 <= passenger_age < 12:
            base_fare *= 0.5
        elif passenger_age >= 60:
            base_fare *= 0.75
        
        # Apply concession discount
        concession_discounts = {
            "student": 0.25,
            "senior_citizen": 0.25,
            "military": 0.20,
            "disabled": 0.50,
        }
        
        applicable_discounts = []
        if concession_type and concession_type in concession_discounts:
            discount_rate = concession_discounts[concession_type]
            base_fare *= (1 - discount_rate)
            applicable_discounts.append(f"{concession_type.replace('_', ' ')} ({int(discount_rate*100)}%)")
        
        # Add GST
        gst_amount = base_fare * 0.05
        total_fare = base_fare + gst_amount
        
        # Cancellation charges vary by time to travel
        if days_until_travel >= 30:
            cancellation_charges = total_fare * 0.10
        elif days_until_travel >= 7:
            cancellation_charges = total_fare * 0.25
        elif days_until_travel >= 1:
            cancellation_charges = total_fare * 0.50
        else:
            cancellation_charges = total_fare * 0.75
        
        return FareCheckResult(
            status=VerificationStatus.VERIFIED,
            base_fare=round(base_fare, 2),
            GST=round(gst_amount, 2),
            total_fare=round(total_fare, 2),
            applicable_discounts=applicable_discounts,
            cancellation_charges=round(cancellation_charges, 2),
            message="Fare verified"
        )
    
    def set_simulated_delay(
        self,
        train_number: str,
        journey_date: date,
        delay_minutes: int
    ):
        """Set simulated delay for a train on specific date (for testing)"""
        journey_key = f"{train_number}_{journey_date.isoformat()}"
        self.simulated_delays[journey_key] = delay_minutes
    
    def set_simulated_cancellation(
        self,
        train_number: str,
        journey_date: date,
        reason: str
    ):
        """Set simulated cancellation for a train on specific date (for testing)"""
        journey_key = f"{train_number}_{journey_date.isoformat()}"
        self.simulated_cancellations[journey_key] = reason
    
    def clear_simulations(self):
        """Clear all simulated delays/cancellations"""
        self.simulated_delays.clear()
        self.simulated_cancellations.clear()


class VerificationService:
    """Service to verify journey details when user "unlocks" details"""
    
    def __init__(self):
        self.data_provider = SimulatedRealTimeDataProvider()
    
    def verify_journey(
        self,
        journey: JourneyOption,
        travel_date: date,
        coach_preference: str = "AC_THREE_TIER",
        passenger_age: int = 30,
        concession_type: Optional[str] = None
    ) -> VerificationDetails:
        """Complete verification of journey when user clicks "Unlock Details"
        
        Args:
            journey: Journey option to verify
            travel_date: Travel date
            coach_preference: Preferred coach type
            passenger_age: Age of passenger
            concession_type: Concession code if applicable
            
        Returns:
            VerificationDetails with all checks
        """
        
        # For multi-segment journeys, verify all segments
        # For simplicity, we'll verify the first segment
        primary_segment = journey.segments[0] if journey.segments else None
        
        if not primary_segment:
            raise ValueError("Journey must have at least one segment")
        
        # Run all verification checks
        seat_check = self.data_provider.verify_seat_availability(
            primary_segment, travel_date, coach_preference
        )
        schedule_check = self.data_provider.verify_train_schedule(
            primary_segment, travel_date
        )
        fare_check = self.data_provider.verify_fare(
            primary_segment, travel_date, passenger_age, concession_type
        )
        
        # Determine overall status and restrictions
        restrictions = []
        warnings = []
        is_bookable = True
        
        if schedule_check.status == VerificationStatus.CANCELLED:
            is_bookable = False
            restrictions.append("Train is cancelled on selected date")
        elif schedule_check.status == VerificationStatus.DELAYED:
            warnings.append(f"Train may arrive {schedule_check.delay_minutes} minutes late")
        
        if seat_check.waiting_list_position and seat_check.available_seats == 0:
            warnings.append(f"No seats available - Waiting List Position: {seat_check.waiting_list_position}")
        elif seat_check.available_seats < 5:
            warnings.append(f"Only {seat_check.available_seats} seats left in preferred class")
        
        # Check if booking is within allowed window
        days_until_travel = (travel_date - date.today()).days
        if days_until_travel > 60:
            restrictions.append("Can only book up to 60 days in advance")
            is_bookable = False
        elif days_until_travel < 0:
            restrictions.append("Cannot book for past dates")
            is_bookable = False
        
        # Determine overall status
        if not is_bookable:
            overall_status = VerificationStatus.FAILED
        elif schedule_check.status == VerificationStatus.DELAYED:
            overall_status = VerificationStatus.DELAYED
        elif seat_check.available_seats == 0:
            overall_status = VerificationStatus.PENDING
        else:
            overall_status = VerificationStatus.VERIFIED
        
        return VerificationDetails(
            journey_id=journey.journey_id,
            verification_timestamp=datetime.now().isoformat(),
            overall_status=overall_status,
            seat_verification=seat_check,
            schedule_verification=schedule_check,
            fare_verification=fare_check,
            restrictions=restrictions,
            warnings=warnings,
            is_bookable=is_bookable
        )
    
    def get_passenger_specific_restrictions(
        self,
        journey: JourneyOption,
        passenger_info: Dict
    ) -> List[str]:
        """Get restrictions specific to passenger type"""
        
        restrictions = []
        age = passenger_info.get("age", 30)
        gender = passenger_info.get("gender", "M")
        
        # Children under 5 must be with adult
        if age < 5:
            restrictions.append("Child below 5 years must be booked with an adult")
        
        # Women can book ladies coaches if available
        if gender == "F":
            if journey.segments[0].ac_first_available > 0:
                restrictions.append("Ladies coaches available")
        
        # Senior citizens may need assistance
        if age >= 70:
            restrictions.append("Assistance available for senior citizens - Contact booking office")
        
        return restrictions
    
    def to_dict(self) -> Dict:
        """Serialize verification details for API response"""
        return {
            "journey_id": self.journey_id,
            "verification_timestamp": self.verification_timestamp,
            "overall_status": self.overall_status.value,
            "is_bookable": self.is_bookable,
            "seats": asdict(self.seat_verification),
            "schedule": asdict(self.schedule_verification),
            "fare": asdict(self.fare_verification),
            "restrictions": self.restrictions,
            "warnings": self.warnings,
        }


# Global instance for offline testing
verification_service = VerificationService()
