"""
Booking Seat Allocator - Integrates Advanced Seat Allocation with Booking Flow
Handles seat preference matching, family grouping, and overbooking decisions
"""
import logging
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from dataclasses import dataclass, field

logger = logging.getLogger("booking.seat_allocator")

@dataclass
class BookingSeatAllocation:
    """Seat allocation result for a booking"""
    success: bool
    seats: List[Dict[str, Any]] = field(default_factory=list)
    coach_assignments: Dict[str, str] = field(default_factory=dict)
    waitlist_position: Optional[int] = None
    is_rac: bool = False
    message: str = ""
    
    def to_dict(self) -> Dict[str, Any]:
        return {
            "success": self.success,
            "seats": self.seats,
            "coach_assignments": self.coach_assignments,
            "waitlist_position": self.waitlist_position,
            "is_rac": self.is_rac,
            "message": self.message
        }


class BookingSeatAllocator:
    """
    Integrates AdvancedSeatAllocationEngine with booking flow.
    Handles preference matching, family grouping, and overbooking.
    """
    
    def __init__(self, db=None):
        self.db = db
        self._allocation_engine = None
    
    def _get_allocation_engine(self):
        """Lazy load allocation engine"""
        if self._allocation_engine is None:
            from services.advanced_seat_allocation_engine import AdvancedSeatAllocationEngine
            self._allocation_engine = AdvancedSeatAllocationEngine()
        return self._allocation_engine
    
    async def allocate_seats_for_booking(
        self,
        train_number: str,
        travel_date: datetime,
        passengers: List[Dict[str, Any]],
        train_class: str = "SL",
        quota: str = "GN",
        preferred_coaches: Optional[List[str]] = None
    ) -> BookingSeatAllocation:
        """
        Allocate seats for a booking based on passenger preferences.
        
        Args:
            train_number: Train number
            travel_date: Travel date
            passengers: List of passenger details
            train_class: Train class (SL, 3A, 2A, 1A)
            quota: Booking quota (GN, Tatkal, Premium Tatkal, etc.)
            preferred_coaches: List of preferred coach types
            
        Returns:
            BookingSeatAllocation with seat assignments
        """
        try:
            # Get train coach configuration
            coaches = await self._get_train_coaches(train_number, train_class)
            
            if not coaches:
                return BookingSeatAllocation(
                    success=False,
                    message="Train coach configuration not available"
                )
            
            # Initialize allocation engine
            engine = self._get_allocation_engine()
            train_id = 0
            try:
                train_id = int(train_number)
            except Exception:
                train_id = 0
            coach_configs = [
                {
                    "coach_id": coach["coach_id"],
                    "class": coach.get("type", train_class),
                    "seats": coach.get("total_seats", 0)
                }
                for coach in coaches
            ]
            engine.initialize_coaches(train_id, coach_configs)
            
            # Check if we need family grouping
            if len(passengers) > 1:
                return await self._allocate_family_seats(
                    engine, passengers, coaches
                )
            else:
                return await self._allocate_individual_seat(
                    engine, passengers[0] if passengers else {}, coaches
                )
                
        except Exception as e:
            logger.error(f"Seat allocation failed: {e}")
            return BookingSeatAllocation(
                success=False,
                message=f"Allocation failed: {str(e)}"
            )
    
    async def _get_train_coaches(self, train_number: str, train_class: str) -> List[Dict]:
        """Get coach configuration for a train from the database."""
        if not self.db:
            raise RuntimeError("Database session required for coach configuration lookup.")

        try:
            from database.models import Trip, Coach, Seat

            trip = self.db.query(Trip).filter(Trip.train_number == train_number).first()
            if not trip:
                raise ValueError(f"No trip found for train number {train_number}")

            coaches = self.db.query(Coach).filter(Coach.trip_id == trip.id).all()
            if not coaches:
                raise ValueError(f"No coach metadata available for train {train_number}")

            coach_configs = []
            for coach in coaches:
                if train_class and coach.class_type and coach.class_type.upper() != train_class.upper():
                    continue

                seat_count = coach.total_seats
                if seat_count is None:
                    seat_count = self.db.query(Seat).filter(Seat.coach_id == coach.id).count()

                available_seats = self.db.query(Seat).filter(
                    Seat.coach_id == coach.id,
                    Seat.is_available == True
                ).count()

                coach_configs.append({
                    "coach_id": coach.coach_number,
                    "type": coach.class_type or train_class,
                    "total_seats": seat_count,
                    "available_seats": available_seats,
                    "cabin_seats": 0
                })

            if not coach_configs:
                # fallback to all coaches if specific class filter produced no matches
                for coach in coaches:
                    seat_count = coach.total_seats
                    if seat_count is None:
                        seat_count = self.db.query(Seat).filter(Seat.coach_id == coach.id).count()
                    available_seats = self.db.query(Seat).filter(
                        Seat.coach_id == coach.id,
                        Seat.is_available == True
                    ).count()
                    coach_configs.append({
                        "coach_id": coach.coach_number,
                        "type": coach.class_type or train_class,
                        "total_seats": seat_count,
                        "available_seats": available_seats,
                        "cabin_seats": 0
                    })

            return coach_configs
        except Exception as e:
            logger.error(f"Failed to load train coaches from DB: {e}")
            return []
    
    async def _allocate_family_seats(
        self,
        engine,
        passengers: List[Dict],
        coaches: List[Dict]
    ) -> BookingSeatAllocation:
        """Allocate seats keeping families together"""
        try:
            # Convert passenger dicts to PassengerPreference format
            from services.advanced_seat_allocation_engine import PassengerPreference, BerthType
            
            family_members = []
            for pax in passengers:
                family_members.append({
                    "name": pax.get("name", ""),
                    "age": int(pax.get("age", 0)) if pax.get("age") is not None else 0,
                })
            group_pnr = passengers[0].get("pnr", "FAMILY") if passengers else "FAMILY"

            result = engine.allocate_family_seats(group_pnr, family_members)
            
            if result.success:
                return BookingSeatAllocation(
                    success=True,
                    seats=result.seats,
                    coach_assignments={result.coach: ", ".join(result.seats)} if result.coach else {},
                    message="Family seats allocated successfully"
                )
            else:
                # Try regular allocation
                return await self._allocate_regular_seats(engine, passengers, coaches)
                
        except Exception as e:
            logger.error(f"Family seat allocation failed: {e}")
            return BookingSeatAllocation(
                success=False,
                message=f"Family allocation failed: {str(e)}"
            )
    
    async def _allocate_individual_seat(
        self,
        engine,
        passenger: Dict,
        coaches: List[Dict]
    ) -> BookingSeatAllocation:
        """Allocate seat for individual passenger"""
        try:
            from services.advanced_seat_allocation_engine import PassengerPreference, BerthType
            
            berth_pref = str(passenger.get("berth_preference", "NO_PREF")).upper()
            berth_type = BerthType.NO_PREFERENCE
            if berth_pref in BerthType.__members__:
                berth_type = BerthType[berth_pref]
            elif berth_pref in ["LOWER", "LB"]:
                berth_type = BerthType.LOWER
            elif berth_pref in ["UPPER", "UB"]:
                berth_type = BerthType.UPPER
            elif berth_pref in ["SIDE_LOWER", "SL"]:
                berth_type = BerthType.SIDE_LOWER
            elif berth_pref in ["SIDE_UPPER", "SU"]:
                berth_type = BerthType.SIDE_UPPER
            
            seat_pref = str(passenger.get("seat_preference", "ANY")).lower()
            window_preference = None
            if "window" in seat_pref:
                window_preference = True
            elif "aisle" in seat_pref:
                window_preference = False

            pref = PassengerPreference(
                berth_type=berth_type,
                window_preference=window_preference,
                is_female=str(passenger.get("gender", "")).lower() == "female",
                is_senior=bool(passenger.get("is_senior_citizen", False)),
                is_disabled=bool(passenger.get("is_handicapped", False)),
                is_child=bool(passenger.get("is_child", False)),
                group_with=passenger.get("group_with", []) or []
            )
            
            # Use fair distribution allocation
            pnr = passenger.get("pnr", passenger.get("id", "INDIVIDUAL"))
            result = engine.allocate_seats_fair_distribution(
                pnr,
                1,
                [pref]
            )
            
            if result.success:
                return BookingSeatAllocation(
                    success=True,
                    seats=result.seats,
                    coach_assignments={result.coach: ", ".join(result.seats)} if result.coach else {},
                    message="Seat allocated successfully"
                )
            else:
                # Check for RAC/Waitlist
                return await self._handle_waitlist(engine, passenger, coaches)
                
        except Exception as e:
            logger.error(f"Individual seat allocation failed: {e}")
            return BookingSeatAllocation(
                success=False,
                message=f"Allocation failed: {str(e)}"
            )
    
    async def _allocate_regular_seats(
        self,
        engine,
        passengers: List[Dict],
        coaches: List[Dict]
    ) -> BookingSeatAllocation:
        """Regular seat allocation without family grouping"""
        from services.advanced_seat_allocation_engine import PassengerPreference, BerthType
        
        passenger_objs = []
        for pax in passengers:
            berth_pref = str(pax.get("berth_preference", "NO_PREF")).upper()
            berth_type = BerthType.NO_PREFERENCE
            if berth_pref in BerthType.__members__:
                berth_type = BerthType[berth_pref]
            elif berth_pref in ["LOWER", "LB"]:
                berth_type = BerthType.LOWER
            elif berth_pref in ["UPPER", "UB"]:
                berth_type = BerthType.UPPER
            elif berth_pref in ["SIDE_LOWER", "SL"]:
                berth_type = BerthType.SIDE_LOWER
            elif berth_pref in ["SIDE_UPPER", "SU"]:
                berth_type = BerthType.SIDE_UPPER

            seat_pref = str(pax.get("seat_preference", "ANY")).lower()
            window_preference = None
            if "window" in seat_pref:
                window_preference = True
            elif "aisle" in seat_pref:
                window_preference = False

            pref = PassengerPreference(
                berth_type=berth_type,
                window_preference=window_preference,
                is_female=str(pax.get("gender", "")).lower() == "female",
                is_senior=bool(pax.get("is_senior_citizen", False)),
                is_disabled=bool(pax.get("is_handicapped", False)),
                is_child=bool(pax.get("is_child", False)),
                group_with=pax.get("group_with", []) or []
            )
            passenger_objs.append(pref)
        
        pnr = passengers[0].get("pnr", "GROUP") if passengers else "GROUP"
        result = engine.allocate_seats_fair_distribution(
            pnr,
            len(passengers),
            passenger_objs
        )
        
        return BookingSeatAllocation(
            success=result.success,
            seats=result.seats,
            coach_assignments={result.coach: ", ".join(result.seats)} if result.coach else {},
            message="Seats allocated" if result.success else "Insufficient availability"
        )
    
    async def _handle_waitlist(
        self,
        engine,
        passenger: Dict,
        coaches: List[Dict]
    ) -> BookingSeatAllocation:
        """Handle waitlist allocation"""
        # Get waitlist position
        waitlist_pos = engine.get_waitlist_position(passenger.get("pnr", ""))
        
        return BookingSeatAllocation(
            success=False,
            waitlist_position=waitlist_pos,
            is_rac=waitlist_pos is not None and waitlist_pos <= 10,
            message=f"Waitlist position: {waitlist_pos}" if waitlist_pos else "No availability"
        )
    
    async def calculate_overbooking_risk(
        self,
        train_number: str,
        travel_date: datetime,
        current_bookings: int,
        total_capacity: int
    ) -> Dict[str, Any]:
        """
        Calculate overbooking risk and suggest strategy.
        
        Returns:
            Dict with risk level, recommended overbook limit, and confidence
        """
        # Calculate current occupancy
        occupancy_rate = current_bookings / total_capacity if total_capacity > 0 else 0
        
        # Get cancellation prediction
        cancellation_rate = await self._predict_cancellation_rate(
            train_number, travel_date
        )
        
        # Calculate risk
        if occupancy_rate >= 0.95:
            risk_level = "HIGH"
            recommended_overbook = 0
        elif occupancy_rate >= 0.85:
            risk_level = "MEDIUM"
            # Suggest limited overbook based on cancellation rate
            recommended_overbook = int(total_capacity * cancellation_rate * 0.5)
        else:
            risk_level = "LOW"
            # Can overbook based on full cancellation prediction
            recommended_overbook = int(total_capacity * cancellation_rate)
        
        return {
            "risk_level": risk_level,
            "occupancy_rate": round(occupancy_rate * 100, 1),
            "predicted_cancellation_rate": round(cancellation_rate * 100, 1),
            "recommended_overbook": min(recommended_overbook, int(total_capacity * 0.05)),
            "confidence": 0.75
        }
    
    async def _predict_cancellation_rate(
        self,
        train_number: str,
        travel_date: datetime
    ) -> float:
        """Predict cancellation rate for a train/date"""
        try:
            from services.cancellation_predictor import CancellationPredictor
            predictor = CancellationPredictor()
            
            # Get prediction
            prediction = predictor.predict_cancellation_rate(
                train_id=int(train_number) if str(train_number).isdigit() else 0,
                travel_date=travel_date.isoformat() if isinstance(travel_date, datetime) else str(travel_date),
                quota_type="general",
                days_to_departure=7,
                booking_velocity=0.0,
                route_popularity=0.5,
                demand_forecast=0.5,
                historical_cancellation_rate=0.08,
            )
            
            return prediction.predicted_cancellation_rate
            
        except Exception as e:
            logger.warning(f"Cancellation prediction failed: {e}")
            # Use default rate (10%)
            return 0.10


# Global instance
_booking_seat_allocator: Optional[BookingSeatAllocator] = None

def get_booking_seat_allocator(db=None) -> BookingSeatAllocator:
    """Get or create global seat allocator instance"""
    global _booking_seat_allocator
    if _booking_seat_allocator is None:
        _booking_seat_allocator = BookingSeatAllocator(db)
    return _booking_seat_allocator