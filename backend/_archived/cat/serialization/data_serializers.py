"""
Pydantic serializers for CAT data models.
Handles JSON serialization/deserialization with custom encoders for
datetime, UUID, and other complex types.
"""

import json
import uuid
from datetime import datetime, date
from typing import Any, Dict, List, Optional, Type, Union

import torch
from pydantic import BaseModel, ConfigDict, Field, field_serializer, model_serializer
from pydantic.json import pydantic_encoder

from ..models.schemas import (
    ContextualData, EventCalendarData, CalendarEvent, Location,
    WeatherData, WeatherConditions, WeatherForecast, HistoricalAvailabilityData,
    AvailabilityRecord, ContextualFactors, AvailabilityPrediction,
    ContributingFactor, PredictionRequest, BatchPredictionRequest,
    BatchPredictionResponse, ServiceHealth, LocationInfo, Season, EventType, WeatherType
)


class DateTimeEncoder:
    """Custom encoder for datetime objects."""
    
    @staticmethod
    def encode(dt: datetime) -> str:
        """Encode datetime to ISO format string."""
        if dt is None:
            return None
        return dt.isoformat()
    
    @staticmethod
    def decode(dt_str: str) -> datetime:
        """Decode ISO format string to datetime."""
        if dt_str is None:
            return None
        # Handle various ISO formats
        if dt_str.endswith('Z'):
            dt_str = dt_str[:-1] + '+00:00'
        return datetime.fromisoformat(dt_str)


class UUIDEncoder:
    """Custom encoder for UUID objects."""
    
    @staticmethod
    def encode(uid: uuid.UUID) -> str:
        """Encode UUID to string."""
        if uid is None:
            return None
        return str(uid)
    
    @staticmethod
    def decode(uid_str: str) -> uuid.UUID:
        """Decode string to UUID."""
        if uid_str is None:
            return None
        return uuid.UUID(uid_str)


class EnumEncoder:
    """Custom encoder for enum objects."""
    
    @staticmethod
    def encode(enum_value: Any) -> str:
        """Encode enum to string value."""
        if enum_value is None:
            return None
        return str(enum_value.value) if hasattr(enum_value, 'value') else str(enum_value)
    
    @staticmethod
    def decode(enum_type: Type, value: str) -> Any:
        """Decode string to enum value."""
        if value is None:
            return None
        return enum_type(value)


class PydanticSerializer:
    """
    Centralized serializer for CAT Pydantic models.
    
    Provides consistent serialization/deserialization with custom encoders
    for datetime, UUID, and enum types.
    """
    
    @staticmethod
    def to_json(obj: BaseModel, indent: int = None, **kwargs) -> str:
        """
        Serialize a Pydantic model to JSON string.
        
        Args:
            obj: Pydantic model instance
            indent: Indentation level for pretty printing
            **kwargs: Additional arguments to pass to json.dumps
            
        Returns:
            JSON string representation
        """
        # Use model_dump() which handles Pydantic v2 serialization
        data = obj.model_dump(mode='json', **kwargs)
        return json.dumps(data, indent=indent, default=pydantic_encoder)
    
    @classmethod
    def from_json(cls, json_str: str, model_class: Type[BaseModel], **kwargs) -> BaseModel:
        """
        Deserialize JSON string to Pydantic model.
        
        Args:
            json_str: JSON string to deserialize
            model_class: Pydantic model class to deserialize to
            **kwargs: Additional arguments to pass to model_validate
            
        Returns:
            Deserialized model instance
        """
        data = json.loads(json_str)
        return model_class.model_validate(data, **kwargs)
    
    @staticmethod
    def to_dict(obj: BaseModel, **kwargs) -> Dict:
        """
        Serialize Pydantic model to dictionary.
        
        Args:
            obj: Pydantic model instance
            **kwargs: Additional arguments to pass to model_dump
            
        Returns:
            Dictionary representation
        """
        return obj.model_dump(mode='json', **kwargs)
    
    @classmethod
    def from_dict(cls, data: Dict, model_class: Type[BaseModel], **kwargs) -> BaseModel:
        """
        Deserialize dictionary to Pydantic model.
        
        Args:
            data: Dictionary to deserialize
            model_class: Pydantic model class to deserialize to
            **kwargs: Additional arguments to pass to model_validate
            
        Returns:
            Deserialized model instance
        """
        return model_class.model_validate(data, **kwargs)


class ContextualDataSerializer:
    """
    Specialized serializer for ContextualData with custom handling.
    """
    
    @staticmethod
    def serialize_contextual_data(data: ContextualData) -> Dict[str, Any]:
        """
        Serialize ContextualData to dictionary with custom encoders.
        
        Args:
            data: ContextualData instance
            
        Returns:
            Dictionary with serialized data
        """
        result = {
            'event_calendar': ContextualDataSerializer._serialize_event_calendar(data.event_calendar),
            'weather': ContextualDataSerializer._serialize_weather(data.weather),
            'historical_availability': ContextualDataSerializer._serialize_historical_availability(data.historical_availability),
            'timestamp': DateTimeEncoder.encode(data.timestamp)
        }
        return result
    
    @staticmethod
    def deserialize_contextual_data(data: Dict[str, Any]) -> ContextualData:
        """
        Deserialize dictionary to ContextualData.
        
        Args:
            data: Dictionary with serialized data
            
        Returns:
            ContextualData instance
        """
        return ContextualData(
            event_calendar=ContextualDataSerializer._deserialize_event_calendar(data['event_calendar']),
            weather=ContextualDataSerializer._deserialize_weather(data['weather']),
            historical_availability=ContextualDataSerializer._deserialize_historical_availability(data['historical_availability']),
            timestamp=DateTimeEncoder.decode(data['timestamp'])
        )
    
    @staticmethod
    def _serialize_event_calendar(data: EventCalendarData) -> Dict[str, Any]:
        """Serialize EventCalendarData."""
        return {
            'events': [ContextualDataSerializer._serialize_calendar_event(e) for e in data.events],
            'last_updated': DateTimeEncoder.encode(data.last_updated)
        }
    
    @staticmethod
    def _deserialize_event_calendar(data: Dict[str, Any]) -> EventCalendarData:
        """Deserialize EventCalendarData."""
        return EventCalendarData(
            events=[ContextualDataSerializer._deserialize_calendar_event(e) for e in data['events']],
            last_updated=DateTimeEncoder.decode(data['last_updated'])
        )
    
    @staticmethod
    def _serialize_calendar_event(data: CalendarEvent) -> Dict[str, Any]:
        """Serialize CalendarEvent."""
        return {
            'event_id': UUIDEncoder.encode(data.event_id),
            'title': data.title,
            'event_type': EnumEncoder.encode(data.event_type),
            'expected_attendance': data.expected_attendance,
            'location': ContextualDataSerializer._serialize_location(data.location),
            'start_time': DateTimeEncoder.encode(data.start_time),
            'end_time': DateTimeEncoder.encode(data.end_time),
            'is_outdoor': data.is_outdoor
        }
    
    @staticmethod
    def _deserialize_calendar_event(data: Dict[str, Any]) -> CalendarEvent:
        """Deserialize CalendarEvent."""
        return CalendarEvent(
            event_id=UUIDEncoder.decode(data['event_id']),
            title=data['title'],
            event_type=EnumEncoder.decode(EventType, data['event_type']),
            expected_attendance=data['expected_attendance'],
            location=ContextualDataSerializer._deserialize_location(data['location']),
            start_time=DateTimeEncoder.decode(data['start_time']),
            end_time=DateTimeEncoder.decode(data['end_time']),
            is_outdoor=data['is_outdoor']
        )
    
    @staticmethod
    def _serialize_location(data: Location) -> Dict[str, Any]:
        """Serialize Location."""
        return {
            'venue_id': data.venue_id,
            'latitude': data.latitude,
            'longitude': data.longitude,
            'capacity': data.capacity
        }
    
    @staticmethod
    def _deserialize_location(data: Dict[str, Any]) -> Location:
        """Deserialize Location."""
        return Location(
            venue_id=data['venue_id'],
            latitude=data['latitude'],
            longitude=data['longitude'],
            capacity=data['capacity']
        )
    
    @staticmethod
    def _serialize_weather(data: WeatherData) -> Dict[str, Any]:
        """Serialize WeatherData."""
        return {
            'current_conditions': ContextualDataSerializer._serialize_weather_conditions(data.current_conditions) if data.current_conditions else None,
            'forecast': [ContextualDataSerializer._serialize_weather_forecast(f) for f in data.forecast],
            'last_updated': DateTimeEncoder.encode(data.last_updated)
        }
    
    @staticmethod
    def _deserialize_weather(data: Dict[str, Any]) -> WeatherData:
        """Deserialize WeatherData."""
        return WeatherData(
            current_conditions=ContextualDataSerializer._deserialize_weather_conditions(data['current_conditions']) if data.get('current_conditions') else None,
            forecast=[ContextualDataSerializer._deserialize_weather_forecast(f) for f in data['forecast']],
            last_updated=DateTimeEncoder.decode(data['last_updated'])
        )
    
    @staticmethod
    def _serialize_weather_conditions(data: WeatherConditions) -> Dict[str, Any]:
        """Serialize WeatherConditions."""
        return {
            'temperature': data.temperature,
            'humidity': data.humidity,
            'precipitation_probability': data.precipitation_probability,
            'wind_speed': data.wind_speed,
            'weather_type': EnumEncoder.encode(data.weather_type)
        }
    
    @staticmethod
    def _deserialize_weather_conditions(data: Dict[str, Any]) -> WeatherConditions:
        """Deserialize WeatherConditions."""
        return WeatherConditions(
            temperature=data['temperature'],
            humidity=data['humidity'],
            precipitation_probability=data['precipitation_probability'],
            wind_speed=data['wind_speed'],
            weather_type=EnumEncoder.decode(WeatherType, data['weather_type'])
        )
    
    @staticmethod
    def _serialize_weather_forecast(data: WeatherForecast) -> Dict[str, Any]:
        """Serialize WeatherForecast."""
        return {
            'time': DateTimeEncoder.encode(data.time),
            'temperature_high': data.temperature_high,
            'temperature_low': data.temperature_low,
            'precipitation_probability': data.precipitation_probability,
            'weather_type': EnumEncoder.encode(data.weather_type)
        }
    
    @staticmethod
    def _deserialize_weather_forecast(data: Dict[str, Any]) -> WeatherForecast:
        """Deserialize WeatherForecast."""
        return WeatherForecast(
            time=DateTimeEncoder.decode(data['time']),
            temperature_high=data['temperature_high'],
            temperature_low=data['temperature_low'],
            precipitation_probability=data['precipitation_probability'],
            weather_type=EnumEncoder.decode(WeatherType, data['weather_type'])
        )
    
    @staticmethod
    def _serialize_historical_availability(data: HistoricalAvailabilityData) -> Dict[str, Any]:
        """Serialize HistoricalAvailabilityData."""
        return {
            'records': [ContextualDataSerializer._serialize_availability_record(r) for r in data.records],
            'location_id': data.location_id,
            'time_range_start': DateTimeEncoder.encode(data.time_range_start),
            'time_range_end': DateTimeEncoder.encode(data.time_range_end)
        }
    
    @staticmethod
    def _deserialize_historical_availability(data: Dict[str, Any]) -> HistoricalAvailabilityData:
        """Deserialize HistoricalAvailabilityData."""
        return HistoricalAvailabilityData(
            records=[ContextualDataSerializer._deserialize_availability_record(r) for r in data['records']],
            location_id=data['location_id'],
            time_range_start=DateTimeEncoder.decode(data['time_range_start']),
            time_range_end=DateTimeEncoder.decode(data['time_range_end'])
        )
    
    @staticmethod
    def _serialize_availability_record(data: AvailabilityRecord) -> Dict[str, Any]:
        """Serialize AvailabilityRecord."""
        return {
            'timestamp': DateTimeEncoder.encode(data.timestamp),
            'available_slots': data.available_slots,
            'total_slots': data.total_slots,
            'utilization_rate': data.utilization_rate,
            'contextual_factors': ContextualDataSerializer._serialize_contextual_factors(data.contextual_factors)
        }
    
    @staticmethod
    def _deserialize_availability_record(data: Dict[str, Any]) -> AvailabilityRecord:
        """Deserialize AvailabilityRecord."""
        return AvailabilityRecord(
            timestamp=DateTimeEncoder.decode(data['timestamp']),
            available_slots=data['available_slots'],
            total_slots=data['total_slots'],
            utilization_rate=data['utilization_rate'],
            contextual_factors=ContextualDataSerializer._deserialize_contextual_factors(data['contextual_factors'])
        )
    
    @staticmethod
    def _serialize_contextual_factors(data: ContextualFactors) -> Dict[str, Any]:
        """Serialize ContextualFactors."""
        return {
            'event_count': data.event_count,
            'weather_severity': data.weather_severity,
            'is_holiday': data.is_holiday,
            'is_weekend': data.is_weekend,
            'season': EnumEncoder.encode(data.season)
        }
    
    @staticmethod
    def _deserialize_contextual_factors(data: Dict[str, Any]) -> ContextualFactors:
        """Deserialize ContextualFactors."""
        return ContextualFactors(
            event_count=data['event_count'],
            weather_severity=data['weather_severity'],
            is_holiday=data['is_holiday'],
            is_weekend=data['is_weekend'],
            season=EnumEncoder.decode(Season, data['season'])
        )


class PredictionSerializer:
    """
    Specialized serializer for AvailabilityPrediction with custom handling.
    """
    
    @staticmethod
    def serialize_prediction(data: AvailabilityPrediction) -> Dict[str, Any]:
        """
        Serialize AvailabilityPrediction to dictionary.
        
        Args:
            data: AvailabilityPrediction instance
            
        Returns:
            Dictionary with serialized data
        """
        return {
            'probability': data.probability,
            'confidence_interval': list(data.confidence_interval),
            'contributing_factors': [
                {
                    'factor_name': f.factor_name,
                    'importance_score': f.importance_score,
                    'description': f.description
                }
                for f in data.contributing_factors
            ],
            'location_id': data.location_id,
            'prediction_time': DateTimeEncoder.encode(data.prediction_time),
            'model_version': data.model_version
        }
    
    @staticmethod
    def deserialize_prediction(data: Dict[str, Any]) -> AvailabilityPrediction:
        """
        Deserialize dictionary to AvailabilityPrediction.
        
        Args:
            data: Dictionary with serialized data
            
        Returns:
            AvailabilityPrediction instance
        """
        return AvailabilityPrediction(
            probability=data['probability'],
            confidence_interval=tuple(data['confidence_interval']),
            contributing_factors=[
                ContributingFactor(
                    factor_name=f['factor_name'],
                    importance_score=f['importance_score'],
                    description=f.get('description')
                )
                for f in data['contributing_factors']
            ],
            location_id=data['location_id'],
            prediction_time=DateTimeEncoder.decode(data['prediction_time']),
            model_version=data['model_version']
        )


# Convenience functions for common operations
def serialize_model(obj: BaseModel) -> str:
    """
    Serialize a Pydantic model to JSON string.
    
    Args:
        obj: Pydantic model instance
        
    Returns:
        JSON string representation
    """
    return PydanticSerializer.to_json(obj)


def deserialize_model(json_str: str, model_class: Type[BaseModel]) -> BaseModel:
    """
    Deserialize JSON string to Pydantic model.
    
    Args:
        json_str: JSON string to deserialize
        model_class: Pydantic model class to deserialize to
        
    Returns:
        Deserialized model instance
    """
    return PydanticSerializer.from_json(json_str, model_class)


def serialize_to_dict(obj: BaseModel) -> Dict:
    """
    Serialize Pydantic model to dictionary.
    
    Args:
        obj: Pydantic model instance
        
    Returns:
        Dictionary representation
    """
    return PydanticSerializer.to_dict(obj)


def deserialize_from_dict(data: Dict, model_class: Type[BaseModel]) -> BaseModel:
    """
    Deserialize dictionary to Pydantic model.
    
    Args:
        data: Dictionary to deserialize
        model_class: Pydantic model class to deserialize to
        
    Returns:
        Deserialized model instance
    """
    return PydanticSerializer.from_dict(data, model_class)
