"""
Data Models for Contextual Availability Transformer (CAT).

This module defines Pydantic models for all data structures used in the CAT system,
including contextual data, predictions, and model inputs.
"""

from pydantic import BaseModel, Field, validator
from typing import List, Dict, Any, Optional, Tuple
from datetime import datetime
from enum import Enum
import numpy as np


class EventType(Enum):
    """Event types for event calendar data."""
    CONCERT = "CONCERT"
    SPORTS = "SPORTS"
    CONFERENCE = "CONFERENCE"
    FESTIVAL = "FESTIVAL"
    CONVENTION = "CONVENTION"
    HOLIDAY = "HOLIDAY"
    OTHER = "OTHER"


class WeatherType(Enum):
    """Weather types for weather data."""
    CLEAR = "CLEAR"
    CLOUDY = "CLOUDY"
    RAIN = "RAIN"
    SNOW = "SNOW"
    STORM = "STORM"
    FOG = "FOG"
    WINDY = "WINDY"


class Season(Enum):
    """Season types for historical data."""
    SPRING = "SPRING"
    SUMMER = "SUMMER"
    FALL = "FALL"
    WINTER = "WINTER"


class Location(BaseModel):
    """Location information."""
    venue_id: str
    latitude: float = Field(..., ge=-90, le=90)
    longitude: float = Field(..., ge=-180, le=180)
    capacity: int = Field(..., gt=0)


class CalendarEvent(BaseModel):
    """Event calendar entry."""
    event_id: str
    title: str
    event_type: EventType
    expected_attendance: int = Field(..., gt=0)
    location: Location
    start_time: datetime
    end_time: datetime
    is_outdoor: bool

    @validator('expected_attendance')
    def validate_attendance(cls, v, values):
        """Validate expected attendance doesn't exceed venue capacity."""
        if 'location' in values and v > values['location'].capacity:
            raise ValueError('expected_attendance cannot exceed venue capacity')
        return v


class EventCalendarData(BaseModel):
    """Event calendar data."""
    events: List[CalendarEvent] = []
    last_updated: datetime = Field(default_factory=datetime.now)

    @validator('last_updated')
    def validate_recent(cls, v):
        """Validate data is within last 24 hours."""
        if (datetime.now() - v).total_seconds() > 86400:
            raise ValueError('last_updated must be within last 24 hours')
        return v


class WeatherConditions(BaseModel):
    """Current weather conditions."""
    temperature: float = Field(..., ge=-50, le=60)
    humidity: float = Field(..., ge=0, le=100)
    precipitation_probability: float = Field(..., ge=0, le=1)
    wind_speed: float = Field(..., ge=0)
    weather_type: WeatherType


class WeatherForecast(BaseModel):
    """Weather forecast entry."""
    time: datetime
    temperature_high: float = Field(..., ge=-50, le=60)
    temperature_low: float = Field(..., ge=-50, le=60)
    precipitation_probability: float = Field(..., ge=0, le=1)
    weather_type: WeatherType


class WeatherData(BaseModel):
    """Weather data."""
    current_conditions: WeatherConditions
    forecast: List[WeatherForecast] = []
    last_updated: datetime = Field(default_factory=datetime.now)

    @validator('last_updated')
    def validate_recent(cls, v):
        """Validate data is within last hour."""
        if (datetime.now() - v).total_seconds() > 3600:
            raise ValueError('last_updated must be within last hour')
        return v


class ContextualFactors(BaseModel):
    """Contextual factors for historical availability."""
    event_count: int = Field(..., ge=0)
    weather_severity: int = Field(..., ge=0, le=5)
    is_holiday: bool
    is_weekend: bool
    season: Season


class AvailabilityRecord(BaseModel):
    """Historical availability record."""
    timestamp: datetime
    available_slots: int = Field(..., ge=0)
    total_slots: int = Field(..., gt=0)
    utilization_rate: float = Field(..., ge=0, le=1)
    contextual_factors: ContextualFactors

    @validator('available_slots')
    def validate_slots(cls, v, values):
        """Validate available slots is within total slots."""
        if 'total_slots' in values and v > values['total_slots']:
            raise ValueError('available_slots cannot exceed total_slots')
        return v


class HistoricalAvailabilityData(BaseModel):
    """Historical availability data."""
    records: List[AvailabilityRecord] = []
    location_id: str
    time_range: Dict[str, datetime] = Field(default_factory=dict)

    @validator('records')
    def validate_records(cls, v):
        """Validate records have valid utilization rates."""
        for record in v:
            if not (0 <= record.utilization_rate <= 1):
                raise ValueError('utilization_rate must be in range [0, 1]')
        return v


class ContextualData(BaseModel):
    """Combined contextual data from all sources."""
    event_calendar: EventCalendarData
    weather: WeatherData
    historical_availability: HistoricalAvailabilityData
    timestamp: datetime = Field(default_factory=datetime.now)


class AvailabilityPrediction(BaseModel):
    """Availability prediction output."""
    probability: float = Field(..., ge=0, le=1)
    confidence_interval: Tuple[float, float] = Field(default=(0.0, 1.0))
    contributing_factors: List[Tuple[str, float]] = Field(default_factory=list)

    @validator('confidence_interval')
    def validate_confidence(cls, v):
        """Validate confidence interval bounds."""
        lower, upper = v
        if lower > upper:
            raise ValueError('confidence_interval lower bound must be <= upper bound')
        return v


class ModelInput(BaseModel):
    """Model input tensor data."""
    event_embeddings: List[float]
    weather_embeddings: List[float]
    historical_sequence: List[float]
    temporal_encoding: List[float]

    class Config:
        arbitrary_types_allowed = True


class LocationRegistryEntry(BaseModel):
    """Location registry entry."""
    location_id: str
    location_name: str
    timezone: str
    enabled: bool = True


class PredictionRequest(BaseModel):
    """Prediction request input."""
    location_id: str
    prediction_time: datetime


class BatchPredictionRequest(BaseModel):
    """Batch prediction request input."""
    predictions: List[PredictionRequest]


class HealthCheckResponse(BaseModel):
    """Health check response."""
    status: str
    timestamp: datetime
    model_loaded: bool = False
    external_apis_healthy: bool = True