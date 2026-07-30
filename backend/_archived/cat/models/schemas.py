"""
Core data models for the Contextual Availability Transformer (CAT) system.
Defines Pydantic schemas for contextual data, predictions, and API responses.
"""

from datetime import datetime, timedelta
from enum import Enum
from typing import List, Optional, Tuple
from uuid import UUID, uuid4
import math

from pydantic import BaseModel, Field, field_validator, model_validator
import numpy as np


class EventType(str, Enum):
    """Types of events that can affect availability."""
    CONCERT = "concert"
    SPORTS = "sports"
    CONFERENCE = "conference"
    FESTIVAL = "festival"
    CONVENTION = "convention"
    HOLIDAY = "holiday"
    OTHER = "other"


class WeatherType(str, Enum):
    """Weather conditions that can affect availability."""
    CLEAR = "clear"
    CLOUDY = "cloudy"
    RAIN = "rain"
    SNOW = "snow"
    STORM = "storm"
    FOG = "fog"
    WINDY = "windy"


class Season(str, Enum):
    """Seasonal indicators for historical patterns."""
    SPRING = "spring"
    SUMMER = "summer"
    FALL = "fall"
    WINTER = "winter"


class TrainClass(str, Enum):
    """Railway travel classes."""
    FIRST_AC = "1A"
    SECOND_AC = "2A"
    THIRD_AC = "3A"
    SLEEPER = "SL"


class Location(BaseModel):
    """Geographic location of a venue or parking facility."""
    venue_id: str = Field(..., description="Unique identifier for the venue")
    latitude: float = Field(..., ge=-90.0, le=90.0, description="Latitude coordinate")
    longitude: float = Field(..., ge=-180.0, le=180.0, description="Longitude coordinate")
    capacity: int = Field(..., gt=0, description="Maximum capacity of the location")

    class Config:
        json_schema_extra = {
            "example": {
                "venue_id": "downtown_parking_garage_a",
                "latitude": 40.7128,
                "longitude": -74.0060,
                "capacity": 500
            }
        }


class CalendarEvent(BaseModel):
    """A single event from the event calendar."""
    event_id: UUID = Field(default_factory=uuid4, description="Unique event identifier")
    title: str = Field(..., min_length=1, max_length=500, description="Event title")
    event_type: EventType = Field(..., description="Type of event")
    expected_attendance: int = Field(..., gt=0, description="Expected number of attendees")
    location: Location = Field(..., description="Event location details")
    start_time: datetime = Field(..., description="Event start time")
    end_time: datetime = Field(..., description="Event end time")
    is_outdoor: bool = Field(default=False, description="Whether event is outdoors")

    @field_validator('end_time')
    @classmethod
    def end_time_must_be_after_start(cls, v: datetime, info) -> datetime:
        start_time = info.data.get('start_time')
        if start_time and v <= start_time:
            raise ValueError('end_time must be after start_time')
        return v

    @field_validator('expected_attendance')
    @classmethod
    def attendance_must_not_exceed_capacity(cls, v: int, info) -> int:
        location = info.data.get('location')
        if location and v > location.capacity:
            raise ValueError('expected_attendance cannot exceed venue capacity')
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "event_id": "550e8400-e29b-41d4-a716-446655440000",
                "title": "Summer Music Festival",
                "event_type": "concert",
                "expected_attendance": 5000,
                "location": {
                    "venue_id": "central_park",
                    "latitude": 40.7829,
                    "longitude": -73.9654,
                    "capacity": 10000
                },
                "start_time": "2024-06-15T18:00:00Z",
                "end_time": "2024-06-15T23:00:00Z",
                "is_outdoor": True
            }
        }


class EventCalendarData(BaseModel):
    """Event calendar data for a location and time range."""
    events: List[CalendarEvent] = Field(default_factory=list, description="List of events")
    last_updated: datetime = Field(default_factory=datetime.utcnow, description="When data was last updated")
    error_flag: bool = Field(default=False, description="Whether there was an error fetching data")

    @field_validator('events')
    @classmethod
    def events_must_be_in_time_range(cls, v: List[CalendarEvent]) -> List[CalendarEvent]:
        # Events are validated individually, this is for additional checks if needed
        return v

    class Config:
        json_schema_extra = {
            "example": {
                "events": [
                    {
                        "event_id": "550e8400-e29b-41d4-a716-446655440000",
                        "title": "Summer Music Festival",
                        "event_type": "concert",
                        "expected_attendance": 5000,
                        "location": {
                            "venue_id": "central_park",
                            "latitude": 40.7829,
                            "longitude": -73.9654,
                            "capacity": 10000
                        },
                        "start_time": "2024-06-15T18:00:00Z",
                        "end_time": "2024-06-15T23:00:00Z",
                        "is_outdoor": True
                    }
                ],
                "last_updated": "2024-06-15T12:00:00Z"
            }
        }


class WeatherConditions(BaseModel):
    """Current weather conditions at a location."""
    temperature: float = Field(..., ge=-50.0, le=60.0, description="Temperature in Celsius")
    humidity: float = Field(..., ge=0.0, le=100.0, description="Relative humidity percentage")
    precipitation_probability: float = Field(..., ge=0.0, le=1.0, description="Probability of precipitation")
    wind_speed: float = Field(..., ge=0.0, description="Wind speed in m/s")
    weather_type: WeatherType = Field(..., description="Primary weather condition")

    class Config:
        json_schema_extra = {
            "example": {
                "temperature": 25.5,
                "humidity": 65.0,
                "precipitation_probability": 0.3,
                "wind_speed": 5.2,
                "weather_type": "clear"
            }
        }


class WeatherForecast(BaseModel):
    """Weather forecast for a specific time."""
    time: datetime = Field(..., description="Forecast time")
    temperature_high: float = Field(..., ge=-50.0, le=60.0, description="High temperature")
    temperature_low: float = Field(..., ge=-50.0, le=60.0, description="Low temperature")
    precipitation_probability: float = Field(..., ge=0.0, le=1.0, description="Precipitation probability")
    weather_type: WeatherType = Field(..., description="Weather condition")

    class Config:
        json_schema_extra = {
            "example": {
                "time": "2024-06-15T18:00:00Z",
                "temperature_high": 28.0,
                "temperature_low": 22.0,
                "precipitation_probability": 0.2,
                "weather_type": "clear"
            }
        }


class WeatherData(BaseModel):
    """Weather data for a location and time range."""
    current_conditions: Optional[WeatherConditions] = Field(None, description="Current conditions")
    forecast: List[WeatherForecast] = Field(default_factory=list, description="Weather forecast")
    last_updated: datetime = Field(default_factory=datetime.utcnow, description="When data was last updated")
    error_flag: bool = Field(default=False, description="Whether there was an error fetching data")

    class Config:
        json_schema_extra = {
            "example": {
                "current_conditions": {
                    "temperature": 25.5,
                    "humidity": 65.0,
                    "precipitation_probability": 0.3,
                    "wind_speed": 5.2,
                    "weather_type": "clear"
                },
                "forecast": [],
                "last_updated": "2024-06-15T12:00:00Z"
            }
        }


class ContextualFactors(BaseModel):
    """Contextual factors associated with an availability record."""
    event_count: int = Field(default=0, ge=0, description="Number of nearby events")
    weather_severity: int = Field(default=0, ge=0, le=10, description="Weather severity score (0-10)")
    is_holiday: bool = Field(default=False, description="Whether it's a holiday")
    is_weekend: bool = Field(default=False, description="Whether it's a weekend")
    season: Season = Field(default=Season.SUMMER, description="Current season")

    class Config:
        json_schema_extra = {
            "example": {
                "event_count": 3,
                "weather_severity": 2,
                "is_holiday": False,
                "is_weekend": True,
                "season": "summer"
            }
        }


class AvailabilityRecord(BaseModel):
    """A single historical availability record."""
    timestamp: datetime = Field(..., description="Record timestamp")
    available_slots: int = Field(..., ge=0, description="Number of available slots")
    total_slots: int = Field(..., gt=0, description="Total number of slots")
    utilization_rate: float = Field(..., ge=0.0, le=1.0, description="Utilization rate")
    contextual_factors: ContextualFactors = Field(..., description="Associated contextual factors")

    @field_validator('available_slots')
    @classmethod
    def available_must_not_exceed_total(cls, v: int, info) -> int:
        total = info.data.get('total_slots')
        if total and v > total:
            raise ValueError('available_slots cannot exceed total_slots')
        return v

    @model_validator(mode='after')
    def utilization_rate_matches_slots(self) -> 'AvailabilityRecord':
        if self.total_slots > 0:
            expected_utilization = 1.0 - (self.available_slots / self.total_slots)
            if abs(expected_utilization - self.utilization_rate) > 0.01:
                # Auto-correct utilization rate if it doesn't match slots
                self.utilization_rate = expected_utilization
        return self

    class Config:
        json_schema_extra = {
            "example": {
                "timestamp": "2024-06-15T18:00:00Z",
                "available_slots": 150,
                "total_slots": 500,
                "utilization_rate": 0.7,
                "contextual_factors": {
                    "event_count": 3,
                    "weather_severity": 2,
                    "is_holiday": False,
                    "is_weekend": True,
                    "season": "summer"
                }
            }
        }


class HistoricalAvailabilityData(BaseModel):
    """Historical availability records for a location."""
    records: List[AvailabilityRecord] = Field(default_factory=list, description="Historical records")
    location_id: str = Field(..., description="Location identifier")
    time_range_start: Optional[datetime] = Field(None, description="Start of time range")
    time_range_end: Optional[datetime] = Field(None, description="End of time range")
    error_flag: bool = Field(default=False, description="Whether there was an error fetching data")

    class Config:
        json_schema_extra = {
            "example": {
                "records": [
                    {
                        "timestamp": "2024-06-15T18:00:00Z",
                        "available_slots": 150,
                        "total_slots": 500,
                        "utilization_rate": 0.7,
                        "contextual_factors": {
                            "event_count": 3,
                            "weather_severity": 2,
                            "is_holiday": False,
                            "is_weekend": True,
                            "season": "summer"
                        }
                    }
                ],
                "location_id": "downtown_parking_garage_a",
                "time_range_start": "2024-01-01T00:00:00Z",
                "time_range_end": "2024-06-15T23:59:59Z"
            }
        }


class ContextualData(BaseModel):
    """Combined contextual data from all sources for a prediction request."""
    event_calendar: EventCalendarData = Field(..., description="Event calendar data")
    weather: WeatherData = Field(..., description="Weather data")
    historical_availability: HistoricalAvailabilityData = Field(..., description="Historical availability data")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="When data was collected")

    class Config:
        json_schema_extra = {
            "example": {
                "event_calendar": {
                    "events": [],
                    "last_updated": "2024-06-15T12:00:00Z"
                },
                "weather": {
                    "current_conditions": {
                        "temperature": 25.5,
                        "humidity": 65.0,
                        "precipitation_probability": 0.3,
                        "wind_speed": 5.2,
                        "weather_type": "clear"
                    },
                    "forecast": [],
                    "last_updated": "2024-06-15T12:00:00Z"
                },
                "historical_availability": {
                    "records": [],
                    "location_id": "downtown_parking_garage_a"
                },
                "timestamp": "2024-06-15T12:00:00Z"
            }
        }


class ContributingFactor(BaseModel):
    """A factor that contributed to a prediction."""
    factor_name: str = Field(..., description="Name of the factor")
    importance_score: float = Field(..., ge=0.0, le=1.0, description="Importance score (0-1)")
    description: Optional[str] = Field(None, description="Human-readable description")

    class Config:
        json_schema_extra = {
            "example": {
                "factor_name": "event_impact",
                "importance_score": 0.45,
                "description": "High-attendance concert nearby"
            }
        }


class AvailabilityPrediction(BaseModel):
    """Output prediction from the CAT model."""
    probability: float = Field(..., ge=0.0, le=1.0, description="Predicted availability probability")
    confidence_interval: Tuple[float, float] = Field(
        ..., description="Lower and upper bounds of confidence interval"
    )
    contributing_factors: List[ContributingFactor] = Field(
        default_factory=list, description="Factors that influenced the prediction"
    )
    location_id: str = Field(..., description="Location ID for this prediction")
    prediction_time: datetime = Field(..., description="Time of prediction")
    model_version: str = Field(default="1.0.0", description="Model version used")

    @field_validator('confidence_interval')
    @classmethod
    def confidence_interval_must_be_valid(cls, v: Tuple[float, float]) -> Tuple[float, float]:
        lower, upper = v
        if lower > upper:
            raise ValueError('Lower bound must be <= upper bound')
        if not (0.0 <= lower <= 1.0 and 0.0 <= upper <= 1.0):
            raise ValueError('Confidence interval must be in [0, 1]')
        return v


class RailwayAvailabilityPrediction(BaseModel):
    """Detailed railway availability prediction with class-level granularity."""
    train_id: str = Field(..., description="Unique identifier for the train")
    route_id: str = Field(..., description="Unique identifier for the route")
    departure_time: datetime = Field(..., description="Scheduled departure time")
    
    # Class-wise availability probabilities
    class_availability: dict[TrainClass, float] = Field(
        ..., description="Predicted probability of availability per class"
    )
    
    # Dynamic Fare Predictions (from FDS)
    predicted_fares: dict[TrainClass, float] = Field(
        ..., description="Predicted dynamic fare per class"
    )
    
    overall_confidence: float = Field(..., ge=0.0, le=1.0, description="Model confidence score")
    factors: List[ContributingFactor] = Field(default_factory=list)
    model_version: str = Field(default="2.0.0-tier2")

    class Config:
        json_schema_extra = {
            "example": {
                "probability": 0.65,
                "confidence_interval": [0.55, 0.75],
                "contributing_factors": [
                    {"factor_name": "event_impact", "importance_score": 0.45, "description": "High-attendance concert nearby"},
                    {"factor_name": "weather_impact", "importance_score": 0.25, "description": "Clear weather expected"},
                    {"factor_name": "historical_pattern", "importance_score": 0.30, "description": "Typical weekend evening pattern"}
                ],
                "location_id": "downtown_parking_garage_a",
                "prediction_time": "2024-06-15T18:00:00Z",
                "model_version": "1.0.0"
            }
        }


class PredictionRequest(BaseModel):
    """Request for an availability prediction."""
    location_id: str = Field(..., description="Location ID to predict")
    prediction_time: datetime = Field(..., description="Time to predict availability for")
    context_hours: int = Field(default=24, ge=1, le=168, description="Hours of context data to use")

    class Config:
        json_schema_extra = {
            "example": {
                "location_id": "downtown_parking_garage_a",
                "prediction_time": "2024-06-15T18:00:00Z",
                "context_hours": 24
            }
        }


class BatchPredictionRequest(BaseModel):
    """Request for multiple predictions."""
    predictions: List[PredictionRequest] = Field(..., min_length=1, max_length=100, description="Prediction requests")

    class Config:
        json_schema_extra = {
            "example": {
                "predictions": [
                    {"location_id": "loc_a", "prediction_time": "2024-06-15T18:00:00Z"},
                    {"location_id": "loc_b", "prediction_time": "2024-06-15T19:00:00Z"}
                ]
            }
        }


class BatchPredictionResponse(BaseModel):
    """Response for batch predictions."""
    predictions: List[AvailabilityPrediction] = Field(..., description="Prediction results")
    total_time_ms: float = Field(..., description="Total processing time in milliseconds")
    cached_count: int = Field(default=0, description="Number of predictions from cache")

    class Config:
        json_schema_extra = {
            "example": {
                "predictions": [],
                "total_time_ms": 150.5,
                "cached_count": 1
            }
        }


class HealthStatus(str, Enum):
    """Health check status."""
    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ServiceHealth(BaseModel):
    """Health status of the CAT service."""
    status: HealthStatus = Field(..., description="Overall service status")
    model_loaded: bool = Field(..., description="Whether model is loaded")
    data_freshness_seconds: float = Field(..., description="Age of data in seconds")
    last_prediction_time: Optional[datetime] = Field(None, description="Time of last prediction")
    uptime_seconds: float = Field(..., description="Service uptime in seconds")

    class Config:
        json_schema_extra = {
            "example": {
                "status": "healthy",
                "model_loaded": True,
                "data_freshness_seconds": 120.5,
                "last_prediction_time": "2024-06-15T12:00:00Z",
                "uptime_seconds": 3600.0
            }
        }


class LocationInfo(BaseModel):
    """Information about a monitored location."""
    location_id: str = Field(..., description="Location identifier")
    name: str = Field(..., description="Human-readable name")
    capacity: int = Field(..., description="Total capacity")
    latitude: float = Field(..., description="Latitude coordinate")
    longitude: float = Field(..., description="Longitude coordinate")
    is_active: bool = Field(default=True, description="Whether location is actively monitored")

    class Config:
        json_schema_extra = {
            "example": {
                "location_id": "downtown_parking_garage_a",
                "name": "Downtown Parking Garage A",
                "capacity": 500,
                "latitude": 40.7128,
                "longitude": -74.0060,
                "is_active": True
            }
        }


class LocationListResponse(BaseModel):
    """Response for location list."""
    locations: List[LocationInfo] = Field(..., description="List of locations")
    total_count: int = Field(..., description="Total number of locations")