"""
Synthetic Data Generators for cost-free route generation.

This module provides generators for:
- Train schedules
- Fare data
- Availability data
- User behavior
"""

import random
import numpy as np
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from dataclasses import dataclass, field
from collections import defaultdict


@dataclass
class Station:
    """Represents a railway station."""
    code: str
    name: str
    zone: str
    state: str
    city: str
    latitude: float
    longitude: float
    elevation: int
    station_type: str
    platforms: int
    amenities: List[str]
    connectivity_score: float
    hub_score: float


@dataclass
class TrainSchedule:
    """Represents a train schedule."""
    train_number: str
    train_name: str
    from_station: str
    to_station: str
    departure_time: str
    arrival_time: str
    duration: str
    days_of_week: List[str]
    train_type: str
    classes: List[str]
    base_fare: float
    distance: int


@dataclass
class FareRecord:
    """Represents a fare record."""
    train_number: str
    from_station: str
    to_station: str
    travel_class: str
    base_fare: float
    dynamic_factor: float
    final_fare: float
    booking_class: str
    availability: int
    booking_date: str
    travel_date: str
    days_before_travel: int


@dataclass
class AvailabilityRecord:
    """Represents an availability record."""
    train_number: str
    from_station: str
    to_station: str
    travel_date: str
    travel_class: str
    availability: int
    waiting_list: int
    confirmation_probability: float
    festival_factor: float
    weather_factor: float
    event_factor: float
    seasonal_factor: float
    demand_score: float


@dataclass
class UserBehavior:
    """Represents user behavior data."""
    user_id: str
    session_id: str
    search_timestamp: str
    from_station: str
    to_station: str
    travel_date: str
    travel_class_preference: str
    time_preference: str
    train_type_preference: str
    price_sensitivity: float
    transfer_tolerance: int
    search_results_count: int
    clicked_routes: List[str]
    booked_route: Optional[str]
    booking_completed: bool
    time_to_booking: str
    device_type: str
    platform: str


class TrainScheduleGenerator:
    """
    Generate synthetic train schedules matching real data distributions.
    
    Uses statistical distribution matching and rule-based generation
    to create realistic train schedules for route generation.
    """
    
    # Real data distributions (loaded from real data)
    TRAIN_TYPE_DISTRIBUTION = {
        'Express': 0.60,
        'Superfast': 0.30,
        'Rajdhani': 0.08,
        'Shatabdi': 0.02,
    }
    
    CLASS_DISTRIBUTION = {
        'SL': 0.50,
        '3A': 0.30,
        '2A': 0.15,
        '1A': 0.05,
    }
    
    TRAIN_TYPE_CLASSES = {
        'Express': ['SL', '3A', '2A'],
        'Superfast': ['SL', '3A', '2A', '1A'],
        'Rajdhani': ['1A', '2A', '3A'],
        'Shatabdi': ['CC', 'EC'],
    }
    
    def __init__(self, real_data_path: Optional[str] = None):
        """
        Initialize the generator.
        
        Args:
            real_data_path: Path to real train schedule data for distribution analysis
        """
        self.real_data = []
        self.distributions = {}
        
        if real_data_path:
            self._load_real_data(real_data_path)
            self._calculate_distributions()
    
    def _load_real_data(self, path: str) -> None:
        """Load real train schedule data."""
        # TODO: Load from CSV/JSON/Database
        # For now, use placeholder data
        self.real_data = self._generate_placeholder_real_data()
    
    def _generate_placeholder_real_data(self) -> List[Dict[str, Any]]:
        """Generate placeholder real data for development."""
        return [
            {
                'train_number': '12001',
                'train_name': 'BSP NDLS EXP',
                'from_station': 'NDLS',
                'to_station': 'BCT',
                'departure_time': '06:00',
                'arrival_time': '14:30',
                'duration': '8h 30m',
                'days_of_week': ['Mon', 'Wed', 'Fri'],
                'train_type': 'Express',
                'classes': ['SL', '3A', '2A'],
                'base_fare': 1.0,
                'distance': 1400,
            },
            {
                'train_number': '12002',
                'train_name': 'NDLS BSP EXP',
                'from_station': 'BCT',
                'to_station': 'NDLS',
                'departure_time': '15:00',
                'arrival_time': '23:30',
                'duration': '8h 30m',
                'days_of_week': ['Tue', 'Thu', 'Sat'],
                'train_type': 'Express',
                'classes': ['SL', '3A', '2A'],
                'base_fare': 1.0,
                'distance': 1400,
            },
            # Add more placeholder data
        ]
    
    def _calculate_distributions(self) -> None:
        """Calculate distributions from real data."""
        # Calculate train type distribution
        train_type_counts = defaultdict(int)
        for record in self.real_data:
            train_type_counts[record['train_type']] += 1
        
        total = sum(train_type_counts.values())
        self.distributions['train_type'] = {
            tt: count / total for tt, count in train_type_counts.items()
        }
        
        # Calculate class distribution
        class_counts = defaultdict(int)
        for record in self.real_data:
            for cls in record['classes']:
                class_counts[cls] += 1
        
        total = sum(class_counts.values())
        self.distributions['class'] = {
            cls: count / total for cls, count in class_counts.items()
        }
        
        # Calculate distance distribution
        distances = [record['distance'] for record in self.real_data]
        self.distributions['distance'] = {
            'min': min(distances),
            'max': max(distances),
            'mean': np.mean(distances),
            'std': np.std(distances),
        }
    
    def generate(self, count: int) -> List[TrainSchedule]:
        """
        Generate synthetic train schedules.
        
        Args:
            count: Number of schedules to generate
            
        Returns:
            List of TrainSchedule objects
        """
        schedules = []
        for _ in range(count):
            schedule = self._generate_single_schedule()
            schedules.append(schedule)
        return schedules
    
    def _generate_single_schedule(self) -> TrainSchedule:
        """Generate a single train schedule."""
        # Sample train type
        train_type = self._sample_train_type()
        
        # Sample stations
        from_station = self._sample_station()
        to_station = self._sample_station(exclude=[from_station])
        
        # Generate times
        departure_time = self._generate_departure_time(train_type)
        arrival_time = self._generate_arrival_time(departure_time, from_station, to_station)
        
        # Generate classes
        classes = self._generate_classes(train_type)
        
        # Generate distance
        distance = self._generate_distance(from_station, to_station)
        
        # Generate duration
        duration = self._generate_duration(distance, train_type)
        
        # Generate train number
        train_number = self._generate_train_number()
        
        # Generate train name
        train_name = self._generate_train_name(train_type, train_number)
        
        # Generate days of week
        days_of_week = self._generate_days_of_week(train_type)
        
        # Generate base fare
        base_fare = self._generate_base_fare(distance)
        
        return TrainSchedule(
            train_number=train_number,
            train_name=train_name,
            from_station=from_station,
            to_station=to_station,
            departure_time=departure_time,
            arrival_time=arrival_time,
            duration=duration,
            days_of_week=days_of_week,
            train_type=train_type,
            classes=classes,
            base_fare=base_fare,
            distance=distance,
        )
    
    def _sample_train_type(self) -> str:
        """Sample a train type from distribution."""
        train_types = list(self.TRAIN_TYPE_DISTRIBUTION.keys())
        weights = list(self.TRAIN_TYPE_DISTRIBUTION.values())
        return random.choices(train_types, weights=weights)[0]
    
    def _sample_station(self, exclude: List[str] = None) -> str:
        """Sample a station from the station list."""
        # TODO: Load from real station data
        stations = ['NDLS', 'BCT', 'MAS', 'HWH', 'BSB', 'LKO', 'ADI', 'BBS', 'PUNE', 'SUR']
        if exclude:
            stations = [s for s in stations if s not in exclude]
        return random.choice(stations)
    
    def _generate_departure_time(self, train_type: str) -> str:
        """Generate departure time based on train type."""
        # Different train types have different departure patterns
        if train_type in ['Shatabdi', 'Rajdhani']:
            # Premium trains often depart in morning
            hour = random.choice([5, 6, 7, 8])
        else:
            # Express/Superfast can depart at any time
            hour = random.randint(0, 23)
        
        minute = random.choice([0, 15, 30, 45])
        return f"{hour:02d}:{minute:02d}"
    
    def _generate_arrival_time(self, departure: str, from_station: str, to_station: str) -> str:
        """Generate arrival time based on departure and distance."""
        dep_hour, dep_min = map(int, departure.split(':'))
        
        # Estimate travel time based on stations (placeholder)
        distance = abs(hash(from_station + to_station)) % 1000 + 100
        travel_hours = distance // 80  # ~80 km/h average
        
        arr_hour = dep_hour + travel_hours
        arr_min = dep_min
        
        if arr_min >= 60:
            arr_hour += arr_min // 60
            arr_min = arr_min % 60
        
        if arr_hour >= 24:
            arr_hour = arr_hour % 24
        
        return f"{arr_hour:02d}:{arr_min:02d}"
    
    def _generate_classes(self, train_type: str) -> List[str]:
        """Generate available classes based on train type."""
        return self.TRAIN_TYPE_CLASSES.get(train_type, ['SL', '3A', '2A'])
    
    def _generate_distance(self, from_station: str, to_station: str) -> int:
        """Generate distance between stations."""
        # Use hash-based distance estimation (placeholder)
        base_distance = abs(hash(from_station + to_station)) % 1000 + 100
        return base_distance
    
    def _generate_duration(self, distance: int, train_type: str) -> str:
        """Generate duration based on distance and train type."""
        # Different train types have different average speeds
        speeds = {
            'Express': 60,
            'Superfast': 75,
            'Rajdhani': 90,
            'Shatabdi': 100,
        }
        
        speed = speeds.get(train_type, 60)
        travel_hours = distance // speed
        travel_minutes = (distance % speed) * 60 // speed
        
        return f"{travel_hours}h {travel_minutes}m"
    
    def _generate_train_number(self) -> str:
        """Generate a unique train number."""
        # Train numbers typically start with 1-9 and have 4-5 digits
        return str(random.randint(10000, 99999))
    
    def _generate_train_name(self, train_type: str, train_number: str) -> str:
        """Generate train name based on type and number."""
        # Generate name from station codes
        return f"{train_type.upper()} {train_number}"
    
    def _generate_days_of_week(self, train_type: str) -> List[str]:
        """Generate operating days based on train type."""
        days = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun']
        
        # Premium trains often run daily
        if train_type in ['Rajdhani', 'Shatabdi']:
            return days
        
        # Other trains run on specific days
        num_days = random.choice([2, 3, 4])
        return sorted(random.sample(days, num_days))
    
    def _generate_base_fare(self, distance: int) -> float:
        """Generate base fare based on distance."""
        # Base fare ~₹10 per 10km (placeholder)
        return round(distance * 0.10, 2)


class FareGenerator:
    """
    Generate synthetic fare data with dynamic pricing factors.
    
    Uses rule-based generation with ML prediction for realistic
    fare calculations.
    """
    
    # Fare multipliers by class
    CLASS_MULTIPLIERS = {
        'SL': 1.0,
        '3A': 1.5,
        '2A': 2.0,
        '1A': 3.0,
        'CC': 1.2,
        'EC': 1.8,
    }
    
    # Booking class distribution
    BOOKING_CLASS_DISTRIBUTION = {
        'GN': 0.60,  # General
        'TQ': 0.20,  # Tatkal
        'PQ': 0.10,  # Premium
        'FQ': 0.10,  # Festival
    }
    
    def __init__(self, schedule_generator: TrainScheduleGenerator):
        """
        Initialize the fare generator.
        
        Args:
            schedule_generator: TrainScheduleGenerator instance
        """
        self.schedule_generator = schedule_generator
        self.class_multipliers = self.CLASS_MULTIPLIERS.copy()
        self.booking_class_dist = self.BOOKING_CLASS_DISTRIBUTION.copy()
    
    def generate(self, count: int) -> List[FareRecord]:
        """
        Generate synthetic fare records.
        
        Args:
            count: Number of fare records to generate
            
        Returns:
            List of FareRecord objects
        """
        fares = []
        for _ in range(count):
            fare = self._generate_single_fare()
            fares.append(fare)
        return fares
    
    def _generate_single_fare(self) -> FareRecord:
        """Generate a single fare record."""
        # Get schedule
        schedule = self.schedule_generator._generate_single_schedule()
        
        # Sample class
        travel_class = self._sample_class()
        
        # Calculate base fare
        base_fare = self._calculate_base_fare(schedule.distance, travel_class)
        
        # Generate dynamic factor
        dynamic_factor = self._generate_dynamic_factor()
        
        # Calculate final fare
        final_fare = base_fare * dynamic_factor
        
        # Generate booking class
        booking_class = self._sample_booking_class()
        
        # Generate availability
        availability = self._generate_availability()
        
        # Generate dates
        booking_date = self._generate_booking_date()
        travel_date = self._generate_travel_date()
        
        # Generate advance booking
        days_before_travel = self._generate_advance_booking(booking_date, travel_date)
        
        return FareRecord(
            train_number=schedule.train_number,
            from_station=schedule.from_station,
            to_station=schedule.to_station,
            travel_class=travel_class,
            base_fare=base_fare,
            dynamic_factor=dynamic_factor,
            final_fare=round(final_fare, 2),
            booking_class=booking_class,
            availability=availability,
            booking_date=booking_date,
            travel_date=travel_date,
            days_before_travel=days_before_travel,
        )
    
    def _sample_class(self) -> str:
        """Sample a travel class from distribution."""
        classes = list(self.class_multipliers.keys())
        weights = list(self.class_multipliers.values())
        return random.choices(classes, weights=weights)[0]
    
    def _calculate_base_fare(self, distance: int, travel_class: str) -> float:
        """Calculate base fare based on distance and class."""
        base_rate = 10  # ₹10 per 10km
        multiplier = self.class_multipliers.get(travel_class, 1.0)
        return round(distance * base_rate * multiplier / 10, 2)
    
    def _generate_dynamic_factor(self) -> float:
        """Generate dynamic pricing factor."""
        # Dynamic factors typically range from 0.8 to 2.5
        # Use normal distribution centered around 1.0
        factor = np.random.normal(1.0, 0.3)
        return round(max(0.8, min(2.5, factor)), 2)
    
    def _sample_booking_class(self) -> str:
        """Sample a booking class from distribution."""
        booking_classes = list(self.booking_class_dist.keys())
        weights = list(self.booking_class_dist.values())
        return random.choices(booking_classes, weights=weights)[0]
    
    def _generate_availability(self) -> int:
        """Generate availability count."""
        # Availability typically ranges from 0 to 100
        # Use normal distribution
        availability = int(np.random.normal(30, 15))
        return max(0, min(100, availability))
    
    def _generate_booking_date(self) -> str:
        """Generate booking date."""
        # Booking date is typically 0-120 days before travel
        days_before = random.randint(0, 120)
        travel_date = datetime.now() + timedelta(days=days_before + 7)
        return travel_date.strftime('%Y-%m-%d')
    
    def _generate_travel_date(self) -> str:
        """Generate travel date."""
        # Travel date is typically 7-180 days in the future
        days_in_future = random.randint(7, 180)
        travel_date = datetime.now() + timedelta(days=days_in_future)
        return travel_date.strftime('%Y-%m-%d')
    
    def _generate_advance_booking(self, booking_date: str, travel_date: str) -> int:
        """Calculate days before travel."""
        booking = datetime.strptime(booking_date, '%Y-%m-%d')
        travel = datetime.strptime(travel_date, '%Y-%m-%d')
        return (travel - booking).days


class AvailabilityGenerator:
    """
    Generate synthetic availability data with contextual factors.
    
    Uses ML-based prediction with contextual factors (festival, weather, event)
    for realistic availability generation.
    """
    
    def __init__(self, schedule_generator: TrainScheduleGenerator):
        """
        Initialize the availability generator.
        
        Args:
            schedule_generator: TrainScheduleGenerator instance
        """
        self.schedule_generator = schedule_generator
        self.availability_model = self._build_availability_model()
    
    def _build_availability_model(self) -> Dict[str, Any]:
        """Build a simple availability prediction model."""
        # Placeholder model - in production, this would be a trained ML model
        return {
            'base_availability': 30,
            'festival_impact': 1.5,
            'weather_impact': 1.2,
            'event_impact': 1.3,
        }
    
    def generate(self, count: int) -> List[AvailabilityRecord]:
        """
        Generate synthetic availability records.
        
        Args:
            count: Number of availability records to generate
            
        Returns:
            List of AvailabilityRecord objects
        """
        availabilities = []
        for _ in range(count):
            availability = self._generate_single_availability()
            availabilities.append(availability)
        return availabilities
    
    def _generate_single_availability(self) -> AvailabilityRecord:
        """Generate a single availability record."""
        # Get schedule
        schedule = self.schedule_generator._generate_single_schedule()
        
        # Generate travel date
        travel_date = self._generate_travel_date()
        
        # Get contextual factors
        festival_factor = self._get_festival_factor(travel_date)
        weather_factor = self._get_weather_factor(travel_date)
        event_factor = self._get_event_factor(travel_date)
        
        # Calculate demand score
        demand_score = self._calculate_demand_score(
            festival_factor, weather_factor, event_factor
        )
        
        # Generate availability using model
        availability = self._generate_availability_value(demand_score)
        
        # Generate waiting list
        waiting_list = self._generate_waiting_list(availability)
        
        # Generate confirmation probability
        confirmation_probability = self._calculate_confirmation_probability(availability)
        
        # Generate seasonal factor
        seasonal_factor = self._get_seasonal_factor(travel_date)
        
        return AvailabilityRecord(
            train_number=schedule.train_number,
            from_station=schedule.from_station,
            to_station=schedule.to_station,
            travel_date=travel_date,
            travel_class=self._sample_class(),
            availability=availability,
            waiting_list=waiting_list,
            confirmation_probability=confirmation_probability,
            festival_factor=festival_factor,
            weather_factor=weather_factor,
            event_factor=event_factor,
            seasonal_factor=seasonal_factor,
            demand_score=demand_score,
        )
    
    def _get_festival_factor(self, travel_date: str) -> float:
        """Get festival impact factor for travel date."""
        # Placeholder - in production, this would check a festival calendar
        festivals = ['Diwali', 'Holi', 'Eid', 'Christmas', 'New Year']
        if any(festival.lower() in travel_date.lower() for festival in festivals):
            return 1.5  # High demand during festivals
        return 1.0
    
    def _get_weather_factor(self, travel_date: str) -> float:
        """Get weather impact factor for travel date."""
        # Placeholder - in production, this would check weather API
        # Rainy season might reduce demand
        if 'Jun' in travel_date or 'Jul' in travel_date or 'Aug' in travel_date:
            return 0.9  # Slightly lower demand during monsoon
        return 1.0
    
    def _get_event_factor(self, travel_date: str) -> float:
        """Get event impact factor for travel date."""
        # Placeholder - in production, this would check event calendar
        # IPL matches, exams, etc. can affect demand
        return 1.1  # Slightly higher demand due to events
    
    def _calculate_demand_score(self, festival: float, weather: float, event: float) -> float:
        """Calculate overall demand score."""
        # Combine contextual factors
        base_demand = 1.0
        combined = base_demand * festival * weather * event
        return round(min(2.0, max(0.5, combined)), 2)
    
    def _generate_availability_value(self, demand_score: float) -> int:
        """Generate availability value based on demand."""
        # Higher demand = lower availability
        base_availability = 30
        adjusted = int(base_availability / demand_score)
        return max(0, min(100, adjusted))
    
    def _generate_waiting_list(self, availability: int) -> int:
        """Generate waiting list count."""
        if availability > 20:
            return 0
        elif availability > 10:
            return random.randint(1, 10)
        else:
            return random.randint(10, 50)
    
    def _calculate_confirmation_probability(self, availability: int) -> float:
        """Calculate probability of confirmation."""
        if availability > 50:
            return 0.95
        elif availability > 20:
            return 0.75
        elif availability > 10:
            return 0.50
        elif availability > 0:
            return 0.25
        else:
            return 0.05
    
    def _get_seasonal_factor(self, travel_date: str) -> float:
        """Get seasonal impact factor."""
        # Summer and winter vacations have higher demand
        month = travel_date.split('-')[1]  # Extract month
        if month in ['05', '06', '11', '12']:
            return 1.3  # Higher demand during vacations
        return 1.0
    
    def _sample_class(self) -> str:
        """Sample a travel class."""
        classes = ['SL', '3A', '2A', '1A']
        return random.choice(classes)
    
    def _generate_travel_date(self) -> str:
        """Generate travel date."""
        days_in_future = random.randint(7, 180)
        travel_date = datetime.now() + timedelta(days=days_in_future)
        return travel_date.strftime('%Y-%m-%d')


class UserBehaviorGenerator:
    """
    Generate synthetic user behavior data for personalization training.
    
    Uses ML-based generation with persona simulation for realistic
    user behavior patterns.
    """
    
    # Device distribution
    DEVICE_DISTRIBUTION = {
        'Mobile': 0.70,
        'Desktop': 0.25,
        'Tablet': 0.05,
    }
    
    # Platform distribution (for mobile)
    PLATFORM_DISTRIBUTION = {
        'Android': 0.60,
        'iOS': 0.40,
    }
    
    # Class preference distribution
    CLASS_PREFERENCE_DISTRIBUTION = {
        'SL': 0.45,
        '3A': 0.35,
        '2A': 0.15,
        '1A': 0.05,
    }
    
    # Time preference distribution
    TIME_PREFERENCE_DISTRIBUTION = {
        'Morning': 0.30,
        'Afternoon': 0.30,
        'Evening': 0.40,
    }
    
    def __init__(self):
        """Initialize the user behavior generator."""
        self.personas = self._create_personas()
    
    def _create_personas(self) -> List[Dict[str, Any]]:
        """Create user personas from real data patterns."""
        return [
            {
                'user_id': f'user-{i:05d}',
                'class_preference': self._sample_class_preference(),
                'time_preference': self._sample_time_preference(),
                'train_type_preference': random.choice(['Express', 'Superfast', 'Rajdhani']),
                'price_sensitivity': round(np.random.uniform(0.3, 0.9), 2),
                'transfer_tolerance': random.randint(0, 3),
                'device_type': self._sample_device(),
                'platform': self._sample_platform(),
            }
            for i in range(1000)  # 1000 personas
        ]
    
    def _sample_class_preference(self) -> str:
        """Sample class preference."""
        classes = list(self.CLASS_PREFERENCE_DISTRIBUTION.keys())
        weights = list(self.CLASS_PREFERENCE_DISTRIBUTION.values())
        return random.choices(classes, weights=weights)[0]
    
    def _sample_time_preference(self) -> str:
        """Sample time preference."""
        times = list(self.TIME_PREFERENCE_DISTRIBUTION.keys())
        weights = list(self.TIME_PREFERENCE_DISTRIBUTION.values())
        return random.choices(times, weights=weights)[0]
    
    def _sample_device(self) -> str:
        """Sample device type."""
        devices = list(self.DEVICE_DISTRIBUTION.keys())
        weights = list(self.DEVICE_DISTRIBUTION.values())
        return random.choices(devices, weights=weights)[0]
    
    def _sample_platform(self) -> str:
        """Sample platform (for mobile users)."""
        if random.random() < 0.7:  # Mobile user
            platforms = list(self.PLATFORM_DISTRIBUTION.keys())
            weights = list(self.PLATFORM_DISTRIBUTION.values())
            return random.choices(platforms, weights=weights)[0]
        return 'Web'
    
    def generate(self, count: int) -> List[UserBehavior]:
        """
        Generate synthetic user behavior records.
        
        Args:
            count: Number of behavior records to generate
            
        Returns:
            List of UserBehavior objects
        """
        behaviors = []
        for _ in range(count):
            behavior = self._generate_single_behavior()
            behaviors.append(behavior)
        return behaviors
    
    def _generate_single_behavior(self) -> UserBehavior:
        """Generate a single user behavior record."""
        # Sample user from persona
        user = random.choice(self.personas)
        
        # Generate search
        search = self._generate_search(user)
        
        # Generate routes
        routes = self._generate_routes(search, user)
        
        # Generate selection
        selection = self._generate_selection(routes, user)
        
        # Generate booking
        booking = self._generate_booking(selection, user)
        
        return UserBehavior(
            user_id=user['user_id'],
            session_id=self._generate_session_id(),
            search_timestamp=self._generate_search_timestamp(),
            from_station=search['from_station'],
            to_station=search['to_station'],
            travel_date=search['travel_date'],
            travel_class_preference=user['class_preference'],
            time_preference=user['time_preference'],
            train_type_preference=user['train_type_preference'],
            price_sensitivity=user['price_sensitivity'],
            transfer_tolerance=user['transfer_tolerance'],
            search_results_count=len(routes),
            clicked_routes=self._get_clicked_routes(selection),
            booked_route=booking['route_id'] if booking['completed'] else None,
            booking_completed=booking['completed'],
            time_to_booking=self._calculate_time_to_booking(search, booking),
            device_type=user['device_type'],
            platform=user['platform'],
        )
    
    def _generate_search(self, user: Dict[str, Any]) -> Dict[str, Any]:
        """Generate search parameters."""
        # Sample stations
        from_station = random.choice(['NDLS', 'BCT', 'MAS', 'HWH', 'BSB', 'LKO'])
        to_station = random.choice(['NDLS', 'BCT', 'MAS', 'HWH', 'BSB', 'LKO'])
        while to_station == from_station:
            to_station = random.choice(['NDLS', 'BCT', 'MAS', 'HWH', 'BSB', 'LKO'])
        
        # Generate travel date
        days_in_future = random.randint(7, 180)
        travel_date = datetime.now() + timedelta(days=days_in_future)
        
        return {
            'from_station': from_station,
            'to_station': to_station,
            'travel_date': travel_date.strftime('%Y-%m-%d'),
        }
    
    def _generate_routes(self, search: Dict[str, Any], user: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Generate route options."""
        # Generate 5-20 route options
        num_routes = random.randint(5, 20)
        
        routes = []
        for i in range(num_routes):
            route = {
                'route_id': f'route-{i:03d}',
                'train_number': f'{random.randint(10000, 99999)}',
                'from_station': search['from_station'],
                'to_station': search['to_station'],
                'departure_time': f'{random.randint(5, 22):02d}:00',
                'arrival_time': f'{random.randint(6, 23):02d}:00',
                'duration': f'{random.randint(2, 12)}h {random.randint(0, 59)}m',
                'classes': ['SL', '3A', '2A'],
                'availability': random.randint(0, 100),
                'fare': random.randint(500, 5000),
                'ml_score': round(np.random.uniform(0.5, 1.0), 2),
            }
            routes.append(route)
        
        return routes
    
    def _generate_selection(self, routes: List[Dict[str, Any]], user: Dict[str, Any]) -> Dict[str, Any]:
        """Generate route selection."""
        # User selects based on preferences
        # Higher ML score = more likely to be selected
        
        # Sort routes by ML score
        sorted_routes = sorted(routes, key=lambda r: r['ml_score'], reverse=True)
        
        # User might select top 1-3 routes
        num_selections = random.randint(1, min(3, len(sorted_routes)))
        selected_routes = sorted_routes[:num_selections]
        
        return {
            'selected_routes': selected_routes,
            'clicked_route': selected_routes[0] if selected_routes else None,
        }
    
    def _get_clicked_routes(self, selection: Dict[str, Any]) -> List[str]:
        """Get list of clicked route IDs."""
        return [r['route_id'] for r in selection['selected_routes']]
    
    def _generate_booking(self, selection: Dict[str, Any], user: Dict[str, Any]) -> Dict[str, Any]:
        """Generate booking decision."""
        # Probability of booking depends on price sensitivity and availability
        clicked_route = selection['clicked_route']
        
        if not clicked_route:
            return {'completed': False, 'route_id': None}
        
        # Higher price sensitivity = lower booking probability
        base_probability = 0.3
        price_factor = 1.0 - user['price_sensitivity'] * 0.3
        availability_factor = min(1.0, clicked_route['availability'] / 50)
        
        booking_probability = base_probability * price_factor * availability_factor
        
        completed = random.random() < booking_probability
        
        return {
            'completed': completed,
            'route_id': clicked_route['route_id'] if completed else None,
        }
    
    def _generate_session_id(self) -> str:
        """Generate session ID."""
        import uuid
        return str(uuid.uuid4())
    
    def _generate_search_timestamp(self) -> str:
        """Generate search timestamp."""
        now = datetime.now()
        hours_ago = random.randint(0, 24)
        timestamp = now - timedelta(hours=hours_ago)
        return timestamp.strftime('%Y-%m-%dT%H:%M:%S')
    
    def _calculate_time_to_booking(self, search: Dict[str, Any], booking: Dict[str, Any]) -> str:
        """Calculate time from search to booking."""
        if not booking['completed']:
            return '0m'
        
        # Time to booking typically 5-30 minutes
        minutes = random.randint(5, 30)
        return f'{minutes}m'


# Convenience functions for generating large datasets
def generate_train_schedules(count: int = 1000000) -> List[TrainSchedule]:
    """Generate a large number of train schedules."""
    generator = TrainScheduleGenerator()
    return generator.generate(count)


def generate_fares(count: int = 2000000) -> List[FareRecord]:
    """Generate a large number of fare records."""
    schedule_generator = TrainScheduleGenerator()
    fare_generator = FareGenerator(schedule_generator)
    return fare_generator.generate(count)


def generate_availability(count: int = 10000000) -> List[AvailabilityRecord]:
    """Generate a large number of availability records."""
    schedule_generator = TrainScheduleGenerator()
    availability_generator = AvailabilityGenerator(schedule_generator)
    return availability_generator.generate(count)


def generate_user_behavior(count: int = 5000000) -> List[UserBehavior]:
    """Generate a large number of user behavior records."""
    generator = UserBehaviorGenerator()
    return generator.generate(count)