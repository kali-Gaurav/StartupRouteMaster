"""
Synthetic data generator for training the CAT model.
Generates realistic availability patterns based on contextual factors.
"""

import random
import math
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Tuple
from uuid import uuid4

from ..models.schemas import (
    EventType, WeatherType, Season, Location, CalendarEvent,
    EventCalendarData, WeatherConditions, WeatherForecast, WeatherData,
    ContextualFactors, AvailabilityRecord, HistoricalAvailabilityData,
    ContextualData
)
from ..config import settings


class SyntheticDataGenerator:
    """
    Generates synthetic data for training the CAT model.
    
    This generator creates realistic availability patterns that reflect
    how real-world factors like events, weather, and time of day affect
    parking availability. The data is designed to be used when real APIs
    are not available, while still being structured for easy integration
    with real data sources when they become available.
    """
    
    def __init__(
        self,
        num_locations: int = None,
        start_date: datetime = None,
        end_date: datetime = None,
        seed: int = 42
    ):
        """
        Initialize the synthetic data generator.
        
        Args:
            num_locations: Number of locations to generate data for
            start_date: Start date for historical data
            end_date: End date for historical data
            seed: Random seed for reproducibility
        """
        self.num_locations = num_locations or settings.synthetic_num_locations
        self.start_date = start_date or datetime.fromisoformat(settings.synthetic_start_date)
        self.end_date = end_date or datetime.fromisoformat(settings.synthetic_end_date)
        self.seed = seed
        
        random.seed(seed)
        
        # Generate location configurations
        self.locations = self._generate_locations()
        
        # Generate event templates for realistic event patterns
        self.event_templates = self._generate_event_templates()
        
        # Generate weather patterns
        self.weather_patterns = self._generate_weather_patterns()
    
    def _generate_locations(self) -> List[Dict]:
        """Generate synthetic train/route configurations."""
        locations = []
        train_types = [
            "rajdhani_express", "shatabdi_express", "duronto_express", 
            "garib_rath", "mail_express", "passenger_local", "intercity"
        ]
        
        for i in range(self.num_locations):
            train_type = random.choice(train_types)
            
            # Base capacity per class (simplified)
            # Total capacity = 1A + 2A + 3A + SL
            class_capacities = {
                "rajdhani_express": {"1A": 22, "2A": 100, "3A": 200, "SL": 0},
                "shatabdi_express": {"1A": 0, "2A": 100, "3A": 400, "SL": 0},
                "mail_express": {"1A": 10, "2A": 40, "3A": 150, "SL": 500},
                "passenger_local": {"1A": 0, "2A": 0, "3A": 0, "SL": 1000},
            }
            
            cap = class_capacities.get(train_type, {"1A": 0, "2A": 50, "3A": 200, "SL": 400})
            
            # Generate coordinates (India-centric for railway realism)
            lat = random.uniform(8.4, 37.6)
            lon = random.uniform(68.7, 97.25)
            
            locations.append({
                "location_id": f"{train_type}_{i:04d}",
                "name": f"{train_type.replace('_', ' ').title()} Train {i}",
                "location_type": train_type,
                "class_capacities": cap,
                "total_capacity": sum(cap.values()),
                "latitude": lat,
                "longitude": lon,
                "base_demand": random.uniform(0.4, 0.9),  # Higher base demand for trains
                "event_sensitivity": random.uniform(0.8, 2.0),
                "weather_sensitivity": random.uniform(0.2, 0.8), # Weather affects delays more than demand
                "srh_profile": [random.uniform(0, 1) for _ in range(settings.station_heuristic_dim)],
                "route_importance": random.uniform(0.5, 1.5)
            })
        
        return locations
    
    def _generate_event_templates(self) -> List[Dict]:
        """Generate event templates for realistic event patterns."""
        templates = []
        
        # Concert events
        for i in range(20):
            templates.append({
                "title": f"Concert {i}",
                "event_type": EventType.CONCERT,
                "min_attendance": 500,
                "max_attendance": 5000,
                "duration_hours": random.choice([2, 3, 4, 5]),
                "is_outdoor": random.choice([True, False]),
                "day_of_week_pattern": [5, 6],  # More common on weekends
                "seasonal_boost": [5, 6, 7, 8]  # More common in summer
            })
        
        # Sports events
        for i in range(15):
            templates.append({
                "title": f"Sports Game {i}",
                "event_type": EventType.SPORTS,
                "min_attendance": 1000,
                "max_attendance": 20000,
                "duration_hours": random.choice([2, 3, 4]),
                "is_outdoor": random.choice([True, False]),
                "day_of_week_pattern": [0, 3, 6],  # Various days
                "seasonal_boost": []  # Year-round
            })
        
        # Conferences
        for i in range(10):
            templates.append({
                "title": f"Conference {i}",
                "event_type": EventType.CONFERENCE,
                "min_attendance": 100,
                "max_attendance": 2000,
                "duration_hours": random.choice([4, 8, 24]),  # Can be multi-day
                "is_outdoor": False,
                "day_of_week_pattern": [1, 2, 3, 4],  # Weekdays
                "seasonal_boost": [2, 3, 9, 10, 11]  # Spring and fall
            })
        
        # Festivals
        for i in range(8):
            templates.append({
                "title": f"Festival {i}",
                "event_type": EventType.FESTIVAL,
                "min_attendance": 2000,
                "max_attendance": 50000,
                "duration_hours": random.choice([6, 8, 12, 24]),
                "is_outdoor": True,
                "day_of_week_pattern": [5, 6],  # Weekends
                "seasonal_boost": [6, 7, 8]  # Summer
            })
        
        # Holidays (special patterns)
        for holiday_name, month, day in [
            ("New Year", 1, 1),
            ("Independence Day", 7, 4),
            ("Christmas", 12, 25),
            ("Thanksgiving", 11, 24)
        ]:
            templates.append({
                "title": f"{holiday_name} Holiday",
                "event_type": EventType.HOLIDAY,
                "min_attendance": 100,
                "max_attendance": 1000,
                "duration_hours": 24,
                "is_outdoor": random.choice([True, False]),
                "day_of_week_pattern": [],
                "seasonal_boost": [],
                "is_holiday": True,
                "fixed_date": (month, day)
            })
        
        return templates
    
    def _generate_weather_patterns(self) -> Dict[int, Dict]:
        """Generate seasonal weather patterns."""
        patterns = {}
        
        for month in range(1, 13):
            if month in [12, 1, 2]:  # Winter
                patterns[month] = {
                    "temp_mean": random.uniform(-5, 10),
                    "temp_std": random.uniform(3, 8),
                    "precip_mean": random.uniform(0.1, 0.3),
                    "weather_types": [WeatherType.CLEAR, WeatherType.CLOUDY, WeatherType.SNOW, WeatherType.FOG]
                }
            elif month in [3, 4, 5]:  # Spring
                patterns[month] = {
                    "temp_mean": random.uniform(8, 20),
                    "temp_std": random.uniform(5, 10),
                    "precip_mean": random.uniform(0.2, 0.4),
                    "weather_types": [WeatherType.CLEAR, WeatherType.CLOUDY, WeatherType.RAIN, WeatherType.FOG]
                }
            elif month in [6, 7, 8]:  # Summer
                patterns[month] = {
                    "temp_mean": random.uniform(20, 32),
                    "temp_std": random.uniform(4, 8),
                    "precip_mean": random.uniform(0.1, 0.3),
                    "weather_types": [WeatherType.CLEAR, WeatherType.CLOUDY, WeatherType.RAIN, WeatherType.STORM, WeatherType.WINDY]
                }
            else:  # Fall
                patterns[month] = {
                    "temp_mean": random.uniform(5, 18),
                    "temp_std": random.uniform(4, 8),
                    "precip_mean": random.uniform(0.2, 0.4),
                    "weather_types": [WeatherType.CLEAR, WeatherType.CLOUDY, WeatherType.RAIN, WeatherType.FOG]
                }
        
        return patterns
    
    def _get_season(self, date: datetime) -> Season:
        """Get the season for a given date."""
        month = date.month
        if month in [12, 1, 2]:
            return Season.WINTER
        elif month in [3, 4, 5]:
            return Season.SPRING
        elif month in [6, 7, 8]:
            return Season.SUMMER
        else:
            return Season.FALL
    
    def _calculate_class_utilization(
        self,
        location: Dict,
        timestamp: datetime,
        factors: ContextualFactors
    ) -> Dict[str, float]:
        """
        Calculate class-wise utilization (1A, 2A, 3A, SL).
        """
        # Base utilization similar to parking but with class-specific logic
        hour = timestamp.hour
        # Peak demand for trains often at start of journeys or long-distance windows
        time_factor = 0.5 + 0.3 * math.sin((hour - 12) * math.pi / 12)
        
        base_demand = location.get("base_demand", 0.5)
        
        utilization = {}
        for tc in ["1A", "2A", "3A", "SL"]:
            # Logic: SL fills up fastest, 1A has more variance
            class_multiplier = {"1A": 0.7, "2A": 0.85, "3A": 0.95, "SL": 1.1}.get(tc, 1.0)
            
            tc_util = base_demand * time_factor * class_multiplier
            
            # Event impact
            tc_util += min(factors.event_count * 0.15, 0.6) * location.get("event_sensitivity", 1.0)
            
            # Holiday impact (extreme for trains)
            if factors.is_holiday:
                tc_util += 0.4
                
            # Random noise
            tc_util += random.gauss(0, 0.03)
            
            utilization[tc] = max(0.0, min(0.99, tc_util))
        
        return utilization
    
    def _calculate_base_availability(
        self,
        location: Dict,
        timestamp: datetime,
        factors: ContextualFactors
    ) -> float:
        """
        Calculate base availability rate for a location.
        Returns a single float value for utilization rate.
        """
        hour = timestamp.hour
        # Time-based pattern (higher during peak hours)
        time_factor = 0.5 + 0.3 * math.sin((hour - 12) * math.pi / 12)
        
        base_demand = location.get("base_demand", 0.5)
        event_sensitivity = location.get("event_sensitivity", 1.0)
        weather_sensitivity = location.get("weather_sensitivity", 0.5)
        
        # Base utilization
        utilization = base_demand * time_factor
        
        # Event impact
        utilization += min(factors.event_count * 0.15, 0.6) * event_sensitivity
        
        # Weather impact
        utilization += (factors.weather_severity / 10.0) * weather_sensitivity * 0.3
        
        # Holiday impact
        if factors.is_holiday:
            utilization += 0.4
        
        # Weekend impact
        if factors.is_weekend:
            utilization += 0.1
        
        return max(0.0, min(0.99, utilization))

    def _generate_srh_vector(self, location: Dict, timestamp: datetime) -> List[float]:
        """Generate Station Heuristic (SRH) vector."""
        base_srh = location["srh_profile"]
        # Add temporal variation to SRH (e.g., peak hour congestion)
        hour_var = 0.2 * math.sin(timestamp.hour * math.pi / 12)
        return [max(0, min(1, val + hour_var + random.uniform(-0.05, 0.05))) for val in base_srh]

    def _generate_fds_vector(self, location: Dict, timestamp: datetime, utilization: Dict[str, float]) -> List[float]:
        """Generate Fare Dynamic Signal (FDS) vector."""
        # Base fares per class
        base_fares = {"1A": 3000, "2A": 1800, "3A": 1200, "SL": 500}
        
        fds = []
        for tc in ["1A", "2A", "3A", "SL"]:
            util = utilization.get(tc, 0.5)
            # Dynamic pricing logic: higher utilization = higher fare
            dynamic_multiplier = 1.0 + (util ** 2) * 0.5
            fare = base_fares[tc] * dynamic_multiplier
            fds.append(fare)
            
        return fds
    
    def _generate_events_for_location(
        self,
        location: Dict,
        time_range_start: datetime,
        time_range_end: datetime
    ) -> List[CalendarEvent]:
        """Generate synthetic events near a location."""
        events = []
        
        # Determine number of events based on location type
        event_counts = {
            "stadium": (20, 50),
            "festival": (5, 15),
            "shopping_center": (30, 80),
            "downtown_parking": (40, 100),
            "airport": (10, 30),
            "hospital": (5, 15),
            "university": (20, 50),
            "office_building": (5, 20),
            "residential": (2, 10)
        }
        
        min_events, max_events = event_counts.get(
            location["location_type"], (10, 30)
        )
        num_events = random.randint(min_events, max_events)
        
        for _ in range(num_events):
            # Pick a random event template
            template = random.choice(self.event_templates)
            
            # Generate event time
            if template.get("is_holiday"):
                # Fixed date holidays
                month, day = template["fixed_date"]
                year = random.randint(time_range_start.year, time_range_end.year)
                try:
                    event_date = datetime(year, month, day)
                except ValueError:
                    event_date = datetime(year, 12, 25)  # Fallback
            else:
                # Random date in range
                days_range = (time_range_end - time_range_start).days
                event_date = time_range_start + timedelta(
                    days=random.randint(0, days_range)
                )
            
            # Check if date matches pattern
            if template.get("day_of_week_pattern"):
                if event_date.weekday() not in template["day_of_week_pattern"]:
                    continue  # Skip if doesn't match day pattern
            
            if template.get("seasonal_boost"):
                if event_date.month not in template["seasonal_boost"]:
                    continue  # Skip if doesn't match season
            
            # Set time (random hour between 8 AM and 10 PM)
            hour = random.randint(8, 22)
            minute = random.choice([0, 15, 30, 45])
            event_time = event_date.replace(hour=hour, minute=minute, second=0, microsecond=0)
            
            # Skip if outside range
            if event_time < time_range_start or event_time > time_range_end:
                continue
            
            # Generate attendance
            attendance = random.randint(
                template["min_attendance"],
                template["max_attendance"]
            )
            
            # Create event
            event = CalendarEvent(
                event_id=uuid4(),
                title=template["title"],
                event_type=template["event_type"],
                expected_attendance=attendance,
                location=Location(
                    venue_id=location["location_id"],
                    latitude=location["latitude"],
                    longitude=location["longitude"],
                    capacity=location["total_capacity"]
                ),
                start_time=event_time,
                end_time=event_time + timedelta(hours=template["duration_hours"]),
                is_outdoor=template["is_outdoor"]
            )
            
            events.append(event)
        
        return events
    
    def _generate_weather(
        self,
        timestamp: datetime,
        location: Dict
    ) -> WeatherData:
        """Generate synthetic weather data."""
        month = timestamp.month
        pattern = self.weather_patterns[month]
        
        # Generate current conditions
        temperature = random.gauss(pattern["temp_mean"], pattern["temp_std"])
        temperature = max(-50, min(60, temperature))  # Clamp to valid range
        
        humidity = random.gauss(50, 20)
        humidity = max(0, min(100, humidity))
        
        precipitation = min(1.0, max(0, random.gauss(pattern["precip_mean"], 0.1)))
        
        wind_speed = random.gauss(3, 2)
        wind_speed = max(0, wind_speed)
        
        weather_type = random.choice(pattern["weather_types"])
        
        current = WeatherConditions(
            temperature=temperature,
            humidity=humidity,
            precipitation_probability=precipitation,
            wind_speed=wind_speed,
            weather_type=weather_type
        )
        
        # Generate forecast (next 24 hours)
        forecast = []
        for i in range(24):
            forecast_time = timestamp + timedelta(hours=i)
            forecast_month = forecast_time.month
            forecast_pattern = self.weather_patterns[forecast_month]
            
            forecast_temp = random.gauss(forecast_pattern["temp_mean"], forecast_pattern["temp_std"])
            forecast_temp = max(-50, min(60, forecast_temp))
            
            forecast_precip = min(1.0, max(0, random.gauss(forecast_pattern["precip_mean"], 0.1)))
            
            forecast_weather = random.choice(forecast_pattern["weather_types"])
            
            forecast.append(WeatherForecast(
                time=forecast_time,
                temperature_high=forecast_temp + random.uniform(2, 5),
                temperature_low=forecast_temp - random.uniform(2, 5),
                precipitation_probability=forecast_precip,
                weather_type=forecast_weather
            ))
        
        return WeatherData(
            current_conditions=current,
            forecast=forecast,
            last_updated=timestamp
        )
    
    def _calculate_weather_severity(self, weather: WeatherData) -> int:
        """Calculate weather severity score (0-10) from weather data."""
        if not weather.current_conditions:
            return 0
        
        conditions = weather.current_conditions
        severity = 0
        
        # Temperature extremes
        if conditions.temperature < -10 or conditions.temperature > 35:
            severity += 3
        elif conditions.temperature < 0 or conditions.temperature > 30:
            severity += 2
        elif conditions.temperature < 5 or conditions.temperature > 28:
            severity += 1
        
        # Precipitation
        if conditions.weather_type in [WeatherType.SNOW, WeatherType.STORM]:
            severity += 4
        elif conditions.weather_type == WeatherType.RAIN:
            severity += 2
        elif conditions.precipitation_probability > 0.7:
            severity += 1
        
        # Wind
        if conditions.wind_speed > 15:
            severity += 3
        elif conditions.wind_speed > 10:
            severity += 1
        
        return min(10, severity)
    
    def generate_historical_data(
        self,
        location: Dict,
        start_date: datetime = None,
        end_date: datetime = None,
        interval_minutes: int = 15
    ) -> HistoricalAvailabilityData:
        """
        Generate historical availability data for a location.
        
        Args:
            location: Location configuration dict
            start_date: Start of data range
            end_date: End of data range
            interval_minutes: Time interval between records
            
        Returns:
            HistoricalAvailabilityData with synthetic records
        """
        start = start_date or self.start_date
        end = end_date or self.end_date
        
        # Generate events for this location
        events = self._generate_events_for_location(location, start, end)
        
        # Group events by date for efficiency
        events_by_date = {}
        for event in events:
            date_key = event.start_time.date()
            if date_key not in events_by_date:
                events_by_date[date_key] = []
            events_by_date[date_key].append(event)
        
        # Generate records
        records = []
        current_time = start
        
        while current_time <= end:
            # Get contextual factors
            date_key = current_time.date()
            day_events = events_by_date.get(date_key, [])
            
            # Count events happening at this time
            event_count = 0
            for event in day_events:
                if event.start_time <= current_time < event.end_time:
                    event_count += 1
            
            # Generate weather
            weather = self._generate_weather(current_time, location)
            weather_severity = self._calculate_weather_severity(weather)
            
            # Create contextual factors
            factors = ContextualFactors(
                event_count=event_count,
                weather_severity=weather_severity,
                is_holiday=current_time.month == 12 and current_time.day == 25,  # Simple holiday check
                is_weekend=current_time.weekday() >= 5,
                season=self._get_season(current_time)
            )
            
            # Calculate availability
            base_utilization = self._calculate_base_availability(
                location, current_time, factors
            )
            
            # Add some noise
            utilization = base_utilization + random.gauss(0, 0.05)
            utilization = max(0.0, min(0.99, utilization))
            
            # Calculate slots
            total_slots = location["total_capacity"]
            available_slots = int(total_slots * (1 - utilization))
            
            # Create record
            record = AvailabilityRecord(
                timestamp=current_time,
                available_slots=available_slots,
                total_slots=total_slots,
                utilization_rate=utilization,
                contextual_factors=factors
            )
            
            records.append(record)
            
            # Move to next interval
            current_time += timedelta(minutes=interval_minutes)
        
        return HistoricalAvailabilityData(
            records=records,
            location_id=location["location_id"],
            time_range_start=start,
            time_range_end=end
        )
    
    def generate_contextual_data(
        self,
        location: Dict,
        prediction_time: datetime,
        context_hours: int = 24
    ) -> ContextualData:
        """
        Generate complete contextual data for a prediction request.
        
        Args:
            location: Location configuration dict
            prediction_time: Time to predict
            context_hours: Hours of historical context to include
            
        Returns:
            ContextualData with all contextual information
        """
        context_start = prediction_time - timedelta(hours=context_hours)
        
        # Generate historical data
        historical = self.generate_historical_data(
            location,
            start_date=context_start,
            end_date=prediction_time,
            interval_minutes=15
        )
        
        # Generate events
        events = self._generate_events_for_location(
            location,
            context_start - timedelta(hours=6),  # Include events starting before context
            prediction_time + timedelta(hours=context_hours)
        )
        
        # Filter to relevant events
        relevant_events = [
            e for e in events
            if e.end_time > context_start and e.start_time < prediction_time + timedelta(hours=context_hours)
        ]
        
        event_calendar = EventCalendarData(
            events=relevant_events,
            last_updated=prediction_time
        )
        
        # Generate weather
        weather = self._generate_weather(prediction_time, location)
        
        return ContextualData(
            event_calendar=event_calendar,
            weather=weather,
            historical_availability=historical,
            timestamp=prediction_time
        )
    
    def generate_dataset(
        self,
        num_samples: int = None,
        locations: List[Dict] = None
    ) -> Tuple[List[HistoricalAvailabilityData], List[ContextualData]]:
        """
        Generate a complete dataset for training.
        
        Args:
            num_samples: Number of samples to generate
            locations: Specific locations to use (or all if None)
            
        Returns:
            Tuple of (historical_data_list, contextual_data_list)
        """
        num_samples = num_samples or settings.synthetic_data_size
        locs = locations or self.locations
        
        historical_data = []
        contextual_data = []
        
        # Generate data for each location
        for location in locs:
            print(f"Generating data for {location['location_id']}...")
            
            # Generate full historical data
            hist = self.generate_historical_data(location)
            historical_data.append(hist)
            
            # Generate contextual data samples
            num_location_samples = max(1, num_samples // len(locs))
            for _ in range(num_location_samples):
                # Random prediction time
                days_range = (self.end_date - self.start_date).days
                pred_time = self.start_date + timedelta(
                    days=random.randint(0, days_range),
                    hours=random.randint(0, 23),
                    minutes=random.choice([0, 15, 30, 45])
                )
                
                ctx = self.generate_contextual_data(location, pred_time)
                contextual_data.append(ctx)
        
        return historical_data, contextual_data


def generate_synthetic_dataset(
    num_samples: int = None,
    num_locations: int = None,
    start_date: datetime = None,
    end_date: datetime = None,
    seed: int = 42
) -> Tuple[List[HistoricalAvailabilityData], List[ContextualData]]:
    """
    Convenience function to generate a synthetic dataset.
    
    Args:
        num_samples: Number of contextual data samples to generate
        num_locations: Number of locations to include
        start_date: Start date for data generation
        end_date: End date for data generation
        seed: Random seed for reproducibility
        
    Returns:
        Tuple of (historical_data_list, contextual_data_list)
    """
    generator = SyntheticDataGenerator(
        num_locations=num_locations,
        start_date=start_date,
        end_date=end_date,
        seed=seed
    )
    
    return generator.generate_dataset(num_samples=num_samples)


if __name__ == "__main__":
    # Example usage
    print("Generating synthetic dataset...")
    
    generator = SyntheticDataGenerator(
        num_locations=10,
        start_date=datetime(2023, 1, 1),
        end_date=datetime(2024, 1, 1),
        seed=42
    )
    
    # Generate a small dataset for testing
    historical, contextual = generator.generate_dataset(num_samples=1000)
    
    print(f"Generated {len(historical)} location histories")
    print(f"Generated {len(contextual)} contextual samples")
    
    # Show sample
    if contextual:
        sample = contextual[0]
        print(f"\nSample ContextualData:")
        print(f"  Location: {sample.historical_availability.location_id}")
        print(f"  Events: {len(sample.event_calendar.events)}")
        print(f"  Weather: {sample.weather.current_conditions.weather_type if sample.weather.current_conditions else 'N/A'}")
        print(f"  Historical records: {len(sample.historical_availability.records)}")