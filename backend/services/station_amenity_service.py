"""
Station Amenity & Waiting Service
==================================

This service provides comprehensive waiting facilities for passengers
who choose to wait at stations for better travel options.

Features:
1. Waiting lounge access
2. Food and beverages
3. Free language learning
4. Entertainment
5. Medical assistance
6. Charging facilities
7. Rest areas
8. Premium packages

This is part of the crowd control system - by providing good
waiting facilities, we encourage passengers to wait for less
crowded trains.

Author: Algorithm Team
Version: 1.0.0
"""
import logging
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class AmenityType(Enum):
    """Types of station amenities"""
    WAITING_LOUNGE = "waiting_lounge"
    FOOD_COURT = "food_court"
    RESTAURANT = "restaurant"
    CAFE = "cafe"
    CHARGING = "charging"
    WIFI = "wifi"
    RESTROOM = "restroom"
    MEDICAL = "medical"
    LOCKER = "locker"
    Cloakroom = "cloakroom"
    BOOKING_COUNTER = "booking_counter"
    ATM = "atm"
    PHARMACY = "pharmacy"
    NEWS_STAND = "news_stand"
    LANGUAGE_LEARNING = "language_learning"
    ENTERTAINMENT = "entertainment"
    PRAYER_ROOM = "prayer_room"


class LoungeTier(Enum):
    """Waiting lounge tiers"""
    BASIC = "basic"       # Free, basic seating
    STANDARD = "standard" # Rs 50-100/hour
    PREMIUM = "premium"   # Rs 200-500/hour with AC, food
    VIP = "vip"           # Rs 1000+/hour - exclusive


@dataclass
class Amenity:
    """Station amenity details"""
    amenity_id: str
    amenity_type: AmenityType
    name: str
    location: str  # Platform number, area
    
    # Availability
    available: bool = True
    operating_hours: str = "24/7"
    
    # Capacity and current usage
    capacity: int = 0
    current_usage: int = 0
    
    # Pricing (if applicable)
    is_free: bool = False
    price: Optional[float] = None
    price_unit: str = "per_use"  # per_hour, per_use, per_meal
    
    # Quality
    rating: float = 0.0  # 0-5
    reviews_count: int = 0
    
    # Features
    features: List[str] = field(default_factory=list)
    
    @property
    def occupancy_rate(self) -> float:
        """Current occupancy percentage"""
        if self.capacity == 0:
            return 0.0
        return self.current_usage / self.capacity
    
    @property
    def is_crowded(self) -> bool:
        """Whether amenity is currently crowded"""
        return self.occupancy_rate > 0.8


@dataclass
class WaitingPackage:
    """
    Complete waiting package for passengers.
    """
    package_id: str
    name: str
    description: str
    
    # Duration (required)
    duration_hours: int
    
    # Pricing (required - must come before optional fields)
    base_price: float
    
    # Optional fields
    can_extend: bool = True
    amenities_included: List[str] = field(default_factory=list)
    meals_included: int = 0  # Number of meals
    drinks_included: int = 0
    price_per_extra_hour: float = 0
    is_family_friendly: bool = False
    is_business_friendly: bool = False
    is_senior_friendly: bool = False
    rating: float = 0.0
    bookings_count: int = 0
    
    @property
    def total_price(self) -> float:
        """Calculate total price for the package"""
        return self.base_price
    
    @property
    def value_score(self) -> float:
        """Value score - amenities per rupee"""
        return len(self.amenities_included) / max(self.base_price, 1) * 100


@dataclass
class WaitBooking:
    """
    Booking for waiting at station.
    """
    booking_id: str
    passenger_id: str
    station_code: str
    
    # Package
    package: WaitingPackage
    start_time: datetime
    end_time: datetime
    
    # Status
    status: str = "confirmed"  # confirmed, checked_in, completed, cancelled
    
    # Add-ons
    add_ons: List[Dict] = field(default_factory=list)
    
    # Payment
    amount_paid: float = 0.0
    payment_status: str = "pending"
    
    # Check-in
    checked_in_at: Optional[datetime] = None
    checked_out_at: Optional[datetime] = None


class StationAmenityService:
    """
    Service for managing station amenities and waiting bookings.
    
    This is a key part of the crowd control system:
    - Provides comfortable waiting options
    - Encourages passengers to wait for better trains
    - Generates additional revenue for stations
    - Improves passenger satisfaction
    """
    
    # Default packages
    DEFAULT_PACKAGES = [
        WaitingPackage(
            package_id="basic_wait",
            name="Basic Waiting",
            description="Comfortable seating with basic amenities",
            duration_hours=2,
            amenities_included=["seating", "charging", "restroom"],
            base_price=50,
            rating=3.5,
            bookings_count=1000
        ),
        WaitingPackage(
            package_id="standard_wait",
            name="Standard Lounge",
            description="AC lounge with snacks and beverages",
            duration_hours=3,
            can_extend=True,
            amenities_included=["ac_lounge", "snacks", "wifi", "charging", "restroom"],
            meals_included=1,
            base_price=200,
            price_per_extra_hour=50,
            rating=4.2,
            bookings_count=500
        ),
        WaitingPackage(
            package_id="premium_wait",
            name="Premium Lounge",
            description="Luxury lounge with full meal and premium services",
            duration_hours=4,
            can_extend=True,
            amenities_included=["premium_lounge", "full_meal", "premium_wifi", 
                               "charging", "restroom", "newspaper", "tv"],
            meals_included=2,
            drinks_included=3,
            base_price=500,
            price_per_extra_hour=100,
            is_business_friendly=True,
            rating=4.7,
            bookings_count=200
        ),
        WaitingPackage(
            package_id="family_wait",
            name="Family Lounge",
            description="Family-friendly space with kids area",
            duration_hours=4,
            can_extend=True,
            amenities_included=["family_room", "kids_area", "snacks", "wifi", 
                               "charging", "restroom", "entertainment"],
            meals_included=2,
            base_price=400,
            price_per_extra_hour=80,
            is_family_friendly=True,
            rating=4.5,
            bookings_count=150
        ),
        WaitingPackage(
            package_id="senior_wait",
            name="Senior Citizen Lounge",
            description="Comfortable space with assistance",
            duration_hours=4,
            can_extend=True,
            amenities_included=["senior_lounge", "assistance", "snacks", 
                               "wifi", "charging", "restroom", "medical"],
            meals_included=2,
            base_price=250,
            price_per_extra_hour=50,
            is_senior_friendly=True,
            rating=4.6,
            bookings_count=100
        )
    ]
    
    def __init__(self, db=None):
        self.db = db
        self._amenity_cache: Dict[str, List[Amenity]] = {}
        self._active_bookings: Dict[str, WaitBooking] = {}
        self._amenities = []  # List of all amenities
        self._packages = self.DEFAULT_PACKAGES  # Waiting packages
    
    def get_default_packages(self) -> List[WaitingPackage]:
        """Get default waiting packages"""
        return self.DEFAULT_PACKAGES
    
    async def get_station_amenities(
        self,
        station_code: str,
        include_crowd_info: bool = True
    ) -> Dict[str, Any]:
        """
        Get all amenities at a station with current status.
        """
        # Check cache
        if station_code in self._amenity_cache:
            return {
                'station': station_code,
                'amenities': [self._amenity_to_dict(a) for a in self._amenity_cache[station_code]]
            }
        
        # Fetch from database or external service
        amenities = await self._fetch_station_amenities(station_code)
        self._amenity_cache[station_code] = amenities
        
        return {
            'station': station_code,
            'amenities': [self._amenity_to_dict(a) for a in amenities],
            'summary': self._get_amenity_summary(amenities)
        }
    
    async def _fetch_station_amenities(self, station_code: str) -> List[Amenity]:
        """Fetch amenities for a station"""
        # This would integrate with station service
        # For now, return based on station tier
        
        tier1_amenities = [
            Amenity(
                amenity_id=f"{station_code}_lounge_1",
                amenity_type=AmenityType.WAITING_LOUNGE,
                name="Executive Lounge",
                location="Platform 1",
                capacity=50,
                current_usage=20,
                price=300,
                price_unit="per_hour",
                rating=4.5,
                features=["AC", "WiFi", "Snacks", "Charging"]
            ),
            Amenity(
                amenity_id=f"{station_code}_food_1",
                amenity_type=AmenityType.FOOD_COURT,
                name="Food Court",
                location="Platform 2",
                capacity=200,
                current_usage=80,
                is_free=False,
                rating=4.0,
                features=["Multiple cuisines", "Vegetarian options"]
            ),
            Amenity(
                amenity_id=f"{station_code}_charging_1",
                amenity_type=AmenityType.CHARGING,
                name="Charging Station",
                location="Waiting Hall",
                capacity=30,
                current_usage=15,
                is_free=True,
                features=["USB", "AC outlets"]
            ),
            Amenity(
                amenity_id=f"{station_code}_language",
                amenity_type=AmenityType.LANGUAGE_LEARNING,
                name="Language Learning Center",
                location="Waiting Hall",
                capacity=20,
                current_usage=5,
                is_free=True,
                features=["English", "Hindi", "Regional languages", "Audio/Video"]
            )
        ]
        
        return tier1_amenities
    
    def _amenity_to_dict(self, amenity: Amenity) -> Dict:
        """Convert amenity to dictionary"""
        return {
            'id': amenity.amenity_id,
            'type': amenity.amenity_type.value,
            'name': amenity.name,
            'location': amenity.location,
            'available': amenity.available,
            'capacity': amenity.capacity,
            'current_usage': amenity.current_usage,
            'occupancy_rate': amenity.occupancy_rate,
            'is_crowded': amenity.is_crowded,
            'is_free': amenity.is_free,
            'price': amenity.price,
            'rating': amenity.rating,
            'features': amenity.features
        }
    
    def _get_amenity_summary(self, amenities: List[Amenity]) -> Dict:
        """Get summary of amenities"""
        by_type = {}
        for a in amenities:
            if a.amenity_type.value not in by_type:
                by_type[a.amenity_type.value] = 0
            by_type[a.amenity_type.value] += 1
        
        total_capacity = sum(a.capacity for a in amenities)
        total_usage = sum(a.current_usage for a in amenities)
        
        return {
            'total_amenities': len(amenities),
            'by_type': by_type,
            'total_capacity': total_capacity,
            'total_usage': total_usage,
            'overall_occupancy': total_usage / total_capacity if total_capacity > 0 else 0,
            'free_amenities': sum(1 for a in amenities if a.is_free)
        }
    
    async def get_available_packages(
        self,
        station_code: str,
        passenger_count: int = 1,
        duration_hours: int = 2,
        passenger_type: str = "general"  # general, family, senior, business
    ) -> List[WaitingPackage]:
        """
        Get available waiting packages for a station.
        Filters based on passenger type and duration.
        """
        packages = self.DEFAULT_PACKAGES.copy()
        
        # Filter by passenger type
        if passenger_type == "family":
            packages = [p for p in packages if p.is_family_friendly or not p.is_business_friendly]
        elif passenger_type == "senior":
            packages = [p for p in packages if p.is_senior_friendly]
        elif passenger_type == "business":
            packages = [p for p in packages if p.is_business_friendly]
        
        # Filter by duration
        packages = [p for p in packages if p.duration_hours >= duration_hours]
        
        # Sort by value score
        packages.sort(key=lambda x: x.value_score, reverse=True)
        
        return packages
    
    async def book_waiting(
        self,
        passenger_id: str,
        station_code: str,
        package_id: str,
        start_time: datetime,
        passenger_count: int = 1
    ) -> WaitBooking:
        """
        Book a waiting package at a station.
        """
        # Find package
        package = next(
            (p for p in self.DEFAULT_PACKAGES if p.package_id == package_id),
            None
        )
        
        if not package:
            raise ValueError(f"Package not found: {package_id}")
        
        # Calculate price
        total_price = package.base_price * passenger_count
        
        # Create booking
        booking = WaitBooking(
            booking_id=f"wait_{datetime.utcnow().timestamp()}",
            passenger_id=passenger_id,
            station_code=station_code,
            package=package,
            start_time=start_time,
            end_time=start_time + timedelta(hours=package.duration_hours),
            amount_paid=total_price,
            status="confirmed"
        )
        
        # Store booking
        self._active_bookings[booking.booking_id] = booking
        
        return booking
    
    async def check_in(
        self,
        booking_id: str
    ) -> Dict:
        """Check in to waiting lounge"""
        booking = self._active_bookings.get(booking_id)
        
        if not booking:
            raise ValueError("Booking not found")
        
        if booking.status != "confirmed":
            raise ValueError(f"Cannot check in - status: {booking.status}")
        
        booking.status = "checked_in"
        booking.checked_in_at = datetime.utcnow()
        
        return {
            'booking_id': booking_id,
            'status': 'checked_in',
            'check_in_time': booking.checked_in_at.isoformat(),
            'end_time': booking.end_time.isoformat()
        }
    
    async def check_out(
        self,
        booking_id: str
    ) -> Dict:
        """Check out from waiting lounge"""
        booking = self._active_bookings.get(booking_id)
        
        if not booking:
            raise ValueError("Booking not found")
        
        if booking.status != "checked_in":
            raise ValueError(f"Cannot check out - status: {booking.status}")
        
        booking.status = "completed"
        booking.checked_out_at = datetime.utcnow()
        
        # Calculate actual duration
        actual_duration = (booking.checked_out_at - booking.checked_in_at).total_seconds() / 3600
        
        return {
            'booking_id': booking_id,
            'status': 'completed',
            'check_in_time': booking.checked_in_at.isoformat(),
            'check_out_time': booking.checked_out_at.isoformat(),
            'duration_hours': round(actual_duration, 2)
        }
    
    # =========================================================================
    # LANGUAGE LEARNING (Free Service)
    # =========================================================================
    
    async def get_language_courses(
        self,
        station_code: str
    ) -> List[Dict]:
        """
        Get available language learning courses at station.
        This is a FREE service to help passengers utilize wait time productively.
        """
        return [
            {
                'course_id': 'english_basic',
                'name': 'English Basics',
                'language': 'English',
                'level': 'Beginner',
                'duration_minutes': 30,
                'is_free': True,
                'content_type': 'audio',
                'topics': ['Greetings', 'Numbers', 'Directions', 'Shopping']
            },
            {
                'course_id': 'english_advanced',
                'name': 'English for Travel',
                'language': 'English',
                'level': 'Intermediate',
                'duration_minutes': 45,
                'is_free': True,
                'content_type': 'video',
                'topics': ['Booking tickets', 'Asking directions', 'Emergency phrases']
            },
            {
                'course_id': 'hindi_basic',
                'name': 'Hindi Basics',
                'language': 'Hindi',
                'level': 'Beginner',
                'duration_minutes': 30,
                'is_free': True,
                'content_type': 'audio',
                'topics': ['Namaste', 'Numbers', 'Common phrases']
            },
            {
                'course_id': 'regional_intro',
                'name': 'Regional Language Introduction',
                'language': 'Various',
                'level': 'Beginner',
                'duration_minutes': 20,
                'is_free': True,
                'content_type': 'audio',
                'topics': ['Tamil', 'Telugu', 'Bengali', 'Marathi', 'Gujarati']
            }
        ]
    
    async def start_language_lesson(
        self,
        passenger_id: str,
        course_id: str
    ) -> Dict:
        """Start a language learning session"""
        return {
            'session_id': f"lang_{datetime.utcnow().timestamp()}",
            'course_id': course_id,
            'started_at': datetime.utcnow().isoformat(),
            'progress': 0,
            'status': 'in_progress'
        }
    
    # =========================================================================
    # AMENITY RECOMMENDATIONS
    # =========================================================================
    
    async def get_recommended_amenities(
        self,
        station_code: str,
        wait_duration_minutes: int,
        budget: float = 500
    ) -> Dict[str, Any]:
        """
        Get recommended amenities based on wait duration and budget.
        """
        amenities = await self.get_station_amenities(station_code)
        
        recommendations = {
            'wait_duration_minutes': wait_duration_minutes,
            'budget': budget,
            'recommendations': []
        }
        
        # Recommend based on duration
        if wait_duration_minutes < 60:
            # Short wait - suggest free amenities
            recommendations['recommendations'].append({
                'type': 'free',
                'amenities': ['charging', 'wifi', 'language_learning'],
                'estimated_cost': 0
            })
        elif wait_duration_minutes < 180:
            # Medium wait - suggest basic package
            recommendations['recommendations'].append({
                'type': 'package',
                'package': 'basic_wait',
                'estimated_cost': 50
            })
        else:
            # Long wait - suggest premium package
            recommendations['recommendations'].append({
                'type': 'package',
                'package': 'standard_wait',
                'estimated_cost': 200
            })
        
        return recommendations


# Global instance
_amenity_service: Optional[StationAmenityService] = None

def get_station_amenity_service(db=None) -> StationAmenityService:
    """Get or create global amenity service"""
    global _amenity_service
    if _amenity_service is None:
        _amenity_service = StationAmenityService(db)
    return _amenity_service