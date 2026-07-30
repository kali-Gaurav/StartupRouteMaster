"""
Data Collector Component for CAT.

This module handles fetching contextual data from external sources:
- Event Calendar API
- Weather API
- Historical availability database
"""

import asyncio
import aiohttp
from typing import Dict, Any, Optional, List
from datetime import datetime, timedelta
from dataclasses import dataclass
import logging
import redis
import json

from .data_models import (
    ContextualData,
    EventCalendarData,
    WeatherData,
    HistoricalAvailabilityData,
    CalendarEvent,
    WeatherConditions,
    WeatherForecast,
    AvailabilityRecord,
    ContextualFactors,
)

logger = logging.getLogger(__name__)


@dataclass
class APIClientConfig:
    """Configuration for external API clients."""
    api_url: str
    api_key: str
    timeout: int = 30
    max_retries: int = 3
    cache_ttl: int = 300  # 5 minutes default


class EventCalendarClient:
    """Client for Event Calendar API."""
    
    def __init__(self, config: APIClientConfig):
        self.config = config
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def fetch_events(self, location_id: str, time_range: Dict[str, datetime]) -> EventCalendarData:
        """
        Fetch events for a location and time range.
        
        Args:
            location_id: Location identifier
            time_range: Dictionary with 'start' and 'end' datetime keys
            
        Returns:
            EventCalendarData with events
        """
        try:
            url = f"{self.config.api_url}/events"
            params = {
                'location_id': location_id,
                'start': time_range['start'].isoformat(),
                'end': time_range['end'].isoformat(),
            }
            
            headers = {'Authorization': f'Bearer {self.config.api_key}'}
            
            async with self.session.get(url, params=params, headers=headers, timeout=self.config.timeout) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_events_response(data)
                else:
                    logger.warning(f"Event API returned status {response.status}")
                    return EventCalendarData()
                    
        except Exception as e:
            logger.error(f"Error fetching events: {e}")
            return EventCalendarData()
    
    def _parse_events_response(self, data: Dict[str, Any]) -> EventCalendarData:
        """Parse API response into EventCalendarData."""
        events = []
        for event_data in data.get('events', []):
            event = CalendarEvent(
                event_id=event_data['event_id'],
                title=event_data['title'],
                event_type=EventType(event_data['event_type']),
                expected_attendance=event_data['expected_attendance'],
                location=Location(
                    venue_id=event_data['location']['venue_id'],
                    latitude=event_data['location']['latitude'],
                    longitude=event_data['location']['longitude'],
                    capacity=event_data['location']['capacity'],
                ),
                start_time=datetime.fromisoformat(event_data['start_time']),
                end_time=datetime.fromisoformat(event_data['end_time']),
                is_outdoor=event_data.get('is_outdoor', False),
            )
            events.append(event)
        
        return EventCalendarData(events=events)


class WeatherClient:
    """Client for Weather API."""
    
    def __init__(self, config: APIClientConfig):
        self.config = config
        self.session = None
    
    async def __aenter__(self):
        self.session = aiohttp.ClientSession()
        return self
    
    async def __aexit__(self, exc_type, exc_val, exc_tb):
        if self.session:
            await self.session.close()
    
    async def fetch_weather(self, location_id: str, time_range: Dict[str, datetime]) -> WeatherData:
        """
        Fetch weather data for a location and time range.
        
        Args:
            location_id: Location identifier
            time_range: Dictionary with 'start' and 'end' datetime keys
            
        Returns:
            WeatherData with current conditions and forecast
        """
        try:
            url = f"{self.config.api_url}/weather"
            params = {
                'location_id': location_id,
                'start': time_range['start'].isoformat(),
                'end': time_range['end'].isoformat(),
            }
            
            headers = {'Authorization': f'Bearer {self.config.api_key}'}
            
            async with self.session.get(url, params=params, headers=headers, timeout=self.config.timeout) as response:
                if response.status == 200:
                    data = await response.json()
                    return self._parse_weather_response(data)
                else:
                    logger.warning(f"Weather API returned status {response.status}")
                    return WeatherData(current_conditions=WeatherConditions(
                        temperature=20.0,
                        humidity=50.0,
                        precipitation_probability=0.0,
                        wind_speed=5.0,
                        weather_type=WeatherType.CLEAR,
                    ))
                    
        except Exception as e:
            logger.error(f"Error fetching weather: {e}")
            return WeatherData(current_conditions=WeatherConditions(
                temperature=20.0,
                humidity=50.0,
                precipitation_probability=0.0,
                wind_speed=5.0,
                weather_type=WeatherType.CLEAR,
            ))
    
    def _parse_weather_response(self, data: Dict[str, Any]) -> WeatherData:
        """Parse API response into WeatherData."""
        current = data.get('current', {})
        current_conditions = WeatherConditions(
            temperature=current.get('temperature', 20.0),
            humidity=current.get('humidity', 50.0),
            precipitation_probability=current.get('precipitation_probability', 0.0),
            wind_speed=current.get('wind_speed', 5.0),
            weather_type=WeatherType(current.get('weather_type', 'CLEAR')),
        )
        
        forecasts = []
        for forecast_data in data.get('forecast', []):
            forecast = WeatherForecast(
                time=datetime.fromisoformat(forecast_data['time']),
                temperature_high=forecast_data.get('temperature_high', 25.0),
                temperature_low=forecast_data.get('temperature_low', 15.0),
                precipitation_probability=forecast_data.get('precipitation_probability', 0.0),
                weather_type=WeatherType(forecast_data.get('weather_type', 'CLEAR')),
            )
            forecasts.append(forecast)
        
        return WeatherData(
            current_conditions=current_conditions,
            forecast=forecasts,
        )


class HistoricalAvailabilityClient:
    """Client for historical availability database."""
    
    def __init__(self, redis_client: redis.Redis):
        self.redis = redis_client
    
    async def fetch_historical_availability(
        self, 
        location_id: str, 
        time_range: Dict[str, datetime]
    ) -> HistoricalAvailabilityData:
        """
        Fetch historical availability records for a location.
        
        Args:
            location_id: Location identifier
            time_range: Dictionary with 'start' and 'end' datetime keys
            
        Returns:
            HistoricalAvailabilityData with records
        """
        try:
            # Try to get from cache first
            cache_key = f"historical:{location_id}:{time_range['start'].isoformat()}:{time_range['end'].isoformat()}"
            cached = self.redis.get(cache_key)
            
            if cached:
                logger.info(f"Cache hit for historical data: {cache_key}")
                return HistoricalAvailabilityData.parse_raw(cached)
            
            # TODO: Query database for historical data
            # For now, return empty data
            records = []
            
            historical_data = HistoricalAvailabilityData(
                records=records,
                location_id=location_id,
                time_range=time_range,
            )
            
            # Cache for future requests
            self.redis.setex(cache_key, 3600, historical_data.json())
            
            return historical_data
            
        except Exception as e:
            logger.error(f"Error fetching historical availability: {e}")
            return HistoricalAvailabilityData(
                records=[],
                location_id=location_id,
                time_range=time_range,
            )


class DataCollector:
    """
    Unified data collector that fetches contextual data from all sources.
    
    Implements concurrent fetching with timeout handling and graceful degradation.
    """
    
    def __init__(
        self,
        event_api_config: APIClientConfig,
        weather_api_config: APIClientConfig,
        redis_client: redis.Redis,
        fetch_timeout: int = 30,
    ):
        """
        Initialize the data collector.
        
        Args:
            event_api_config: Event Calendar API configuration
            weather_api_config: Weather API configuration
            redis_client: Redis client for caching
            fetch_timeout: Timeout for each API fetch in seconds
        """
        self.event_client = EventCalendarClient(event_api_config)
        self.weather_client = WeatherClient(weather_api_config)
        self.historical_client = HistoricalAvailabilityClient(redis_client)
        self.fetch_timeout = fetch_timeout
    
    async def fetch_contextual_data(
        self, 
        location_id: str, 
        time_range: Dict[str, datetime]
    ) -> ContextualData:
        """
        Fetch contextual data from all sources concurrently.
        
        Args:
            location_id: Location identifier
            time_range: Dictionary with 'start' and 'end' datetime keys
            
        Returns:
            ContextualData with all fetched data
        """
        logger.info(f"Fetching contextual data for location {location_id}")
        
        try:
            # Fetch all data concurrently
            async with self.event_client as event_session, self.weather_client as weather_session:
                # Create tasks for concurrent fetching
                event_task = asyncio.wait_for(
                    self.event_client.fetch_events(location_id, time_range),
                    timeout=self.fetch_timeout
                )
                weather_task = asyncio.wait_for(
                    self.weather_client.fetch_weather(location_id, time_range),
                    timeout=self.fetch_timeout
                )
                historical_task = asyncio.wait_for(
                    self.historical_client.fetch_historical_availability(location_id, time_range),
                    timeout=self.fetch_timeout
                )
                
                # Wait for all tasks
                events, weather, historical = await asyncio.gather(
                    event_task, weather_task, historical_task,
                    return_exceptions=True
                )
                
                # Handle exceptions with fallbacks
                if isinstance(events, Exception):
                    logger.error(f"Event fetch failed: {events}")
                    events = EventCalendarData()
                
                if isinstance(weather, Exception):
                    logger.error(f"Weather fetch failed: {weather}")
                    weather = WeatherData(current_conditions=WeatherConditions(
                        temperature=20.0,
                        humidity=50.0,
                        precipitation_probability=0.0,
                        wind_speed=5.0,
                        weather_type=WeatherType.CLEAR,
                    ))
                
                if isinstance(historical, Exception):
                    logger.error(f"Historical fetch failed: {historical}")
                    historical = HistoricalAvailabilityData(
                        records=[],
                        location_id=location_id,
                        time_range=time_range,
                    )
                
                contextual_data = ContextualData(
                    event_calendar=events,
                    weather=weather,
                    historical_availability=historical,
                )
                
                logger.info(f"Successfully fetched contextual data for {location_id}")
                return contextual_data
                
        except asyncio.TimeoutError:
            logger.error("Contextual data fetch timed out")
            # Return empty data on timeout
            return ContextualData(
                event_calendar=EventCalendarData(),
                weather=WeatherData(current_conditions=WeatherConditions(
                    temperature=20.0,
                    humidity=50.0,
                    precipitation_probability=0.0,
                    wind_speed=5.0,
                    weather_type=WeatherType.CLEAR,
                )),
                historical_availability=HistoricalAvailabilityData(
                    records=[],
                    location_id=location_id,
                    time_range=time_range,
                ),
            )
        except Exception as e:
            logger.error(f"Error fetching contextual data: {e}")
            raise