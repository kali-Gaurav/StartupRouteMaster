"""
The Persistent & Resilient RapidAPI Client for RouteMaster V2.
Upgraded to FAANG-Grade Architecture with Connection Pooling, Rate Limiting, and Pydantic Validation.
[Task 15: Alerting System & Task 9: Caching Layer Alignment]
"""
import asyncio
import logging
import time
from typing import Optional, Dict, Any, List, Union
from datetime import datetime

import aiohttp
from pydantic import ValidationError

from ..base_provider_client import BaseProviderClient
from ..config import config
from ..models import (
    UnifiedLiveStatus, UnifiedAvailability, UnifiedSchedule,
    UnifiedFare, UnifiedFareInfo, UnifiedPNRStatus, UnifiedStation
)
from schemas.rapidapi_models import (
    LiveTrainStatus, Fare, PNRStatus, SeatAvailability, TrainSchedule,
    TrainsByStation, LiveStatus, LiveStation
)
from utils.rate_limiter import RedisTokenBucket
from core.redis_client import async_redis_client

logger = logging.getLogger("provider.rapidapi")

# --- Optimized Constants ---
RAPIDAPI_RATE_LIMIT = 5.0 # Requests per second
RAPIDAPI_BURST_LIMIT = 10
RAPIDAPI_LIMIT_KEY = "rate_limit:rapidapi"

class RapidApiClient(BaseProviderClient):
    """
    High-performance, persistent client for fetching data from the irctc1.p.rapidapi.com API.
    Utilizes global connection pooling and distributed rate limiting.
    """
    def __init__(self):
        super().__init__(name="RapidAPI_IRCTC", provider_config=config)
        self.base_url = f"https://{config.RAPIDAPI_HOST}"
        self.headers = {
            "x-rapidapi-key": config.RAPIDAPI_KEY,
            "x-rapidapi-host": config.RAPIDAPI_HOST,
            "Content-Type": "application/json",
        }
        self.rate_limiter = RedisTokenBucket(async_redis_client)
        self.timeout = aiohttp.ClientTimeout(total=config.DEFAULT_TIMEOUT, connect=5)

    async def _check_rate_limit(self):
        """Enforces rate limiting to avoid 429 errors and protect API budget."""
        allowed, remaining = await self.rate_limiter.is_allowed(
            RAPIDAPI_LIMIT_KEY, 
            RAPIDAPI_RATE_LIMIT, 
            RAPIDAPI_BURST_LIMIT
        )
        if not allowed:
            logger.warning(f"Rate limit hit for RapidAPI. Remaining tokens: {remaining}")
            # Optional: Add small sleep and retry once or throw custom exception
            await asyncio.sleep(1.0) # Adaptive wait
            return await self._check_rate_limit()
        return True

    async def _make_request(self, method: str, endpoint: str, 
                           params: Optional[Dict] = None, 
                           payload: Optional[Dict] = None) -> Optional[Dict]:
        """Centralized robust HTTP request handler."""
        await self._check_rate_limit()
        
        from utils.http_client import HttpClientManager
        session = await HttpClientManager.get_session()
        
        url = f"{self.base_url}{endpoint}"
        start_time = time.time()
        
        try:
            async with session.request(
                method, url, headers=self.headers, params=params, 
                json=payload, timeout=self.timeout
            ) as response:
                latency = time.time() - start_time
                
                if response.status != 200:
                    status_message = await response.text()
                    logger.error(f"RapidAPI endpoint {endpoint} failed ({response.status}). Latency: {latency:.2f}s. Msg: {status_message[:100]}")
                    return None
                    
                data = await response.json()
                logger.debug(f"RapidAPI {endpoint} success. Latency: {latency:.2f}s.")
                return data
                
        except asyncio.TimeoutError:
            logger.error(f"RapidAPI timeout on {endpoint} after {self.timeout.total}s.")
        except aiohttp.ClientError as e:
            logger.error(f"Client error on {endpoint}: {e}")
        except Exception as e:
            logger.error(f"Unexpected error in _make_request to {endpoint}: {e}")
            
        return None

    # --- Implement Abstract Base Interface ---

    async def get_live_status(self, train_number: str, **kwargs) -> Optional[UnifiedLiveStatus]:
        """Fetches live status and transforms it into the Unified model."""
        endpoint = "/api/v1/liveTrainStatus"
        start_day = kwargs.get('start_day', 0)
        params = {"trainNo": train_number, "startDay": start_day}
        
        data = await self._make_request("GET", endpoint, params)
        if data:
            return to_unified_live_status(data, train_date=kwargs.get('train_date', ''))
        return None

    async def get_seat_availability(self, train_number: str, travel_date: str, 
                                    from_station_code: str, to_station_code: str, 
                                    class_code: str, quota: str = "GN", **kwargs) -> Optional[List[Dict[str, Any]]]:
        """Fetches seat availability and transforms it."""
        endpoint = "/api/v2/checkSeatAvailability"
        params = {
            "trainNo": train_number,
            "fromStationCode": from_station_code,
            "toStationCode": to_station_code,
            "date": travel_date,
            "classType": class_code,
            "quota": quota,
        }
        
        data = await self._make_request("GET", endpoint, params)
        if data and data.get("status"):
            return to_unified_availability_list(data, train_number, travel_date, from_station_code, to_station_code)
        return None

    async def get_schedule(self, train_number: str, **kwargs) -> Optional[Dict[str, Any]]:
        """Fetches train schedule and transforms it."""
        endpoint = "/api/v1/getTrainSchedule"
        params = {"trainNo": train_number}
        
        data = await self._make_request("GET", endpoint, params)
        if data and data.get("status"):
            unified = to_unified_schedule(data)
            return unified.model_dump() if unified else None
        return None

    # --- Additional Standard Provider Methods ---

    async def get_fare(self, train_number: str, travel_date: str, 
                         from_station_code: str, to_station_code: str, 
                         class_code: str, quota: str = "GN") -> Optional[UnifiedFare]:
        endpoint = "/api/v2/getFare"
        params = {
            "trainNo": train_number,
            "fromStationCode": from_station_code,
            "toStationCode": to_station_code,
            "date": travel_date, # Some v2 APIs take date, some don't
            "classType": class_code,
            "quota": quota,
        }
        
        data = await self._make_request("GET", endpoint, params)
        if data and data.get("status"):
            return to_unified_fare(data, train_number=train_number, travel_date=travel_date, 
                                 from_station_code=from_station_code, to_station_code=to_station_code)
        return None

    async def get_pnr_status(self, pnr_number: str) -> Optional[UnifiedPNRStatus]:
        endpoint = "/api/v3/getPNRStatus"
        params = {"pnrNumber": pnr_number}
        
        data = await self._make_request("GET", endpoint, params)
        if data and data.get("status"):
            return to_unified_pnr_status(data)
        return None

# --- Transformation functions ---

def to_unified_live_status(raw_data: Dict[str, Any], **kwargs) -> Optional[UnifiedLiveStatus]:
    """Transforms raw v1 liveTrainStatus to UnifiedLiveStatus."""
    if not raw_data: return None
    
    try:
        # v1 response usually has 'data' key or is top-level if simple
        status_payload = raw_data.get("data", raw_data)
        live_model = LiveTrainStatus.model_validate(status_payload)
        
        # Calculate running status
        delay_min = live_model.delay or 0
        status_str = "On Time"
        if delay_min > 0: status_str = "Delayed"
        if isinstance(live_model.status, str) and "cancel" in live_model.status.lower():
            status_str = "Cancelled"
            
        return UnifiedLiveStatus(
            train_number=live_model.train_number or "N/A",
            current_station_name=live_model.current_station,
            status_as_of=datetime.utcnow(), # Ideally parse live_model.last_updated
            delay_minutes=delay_min,
            running_status=status_str,
            data_source="rapidapi",
            confidence_score=0.98
        )
    except Exception as e:
        logger.error(f"Failed to transform live status: {e}")
        return None

def to_unified_availability_list(raw_data: Dict[str, Any], train_no: str, date: str, 
                                 from_stn: str, to_stn: str) -> List[Dict[str, Any]]:
    """Transforms v2 seat availability results."""
    # Internal list of availability dicts used by gateway/service
    try:
        data = raw_data.get("data", [])
        if not isinstance(data, list): data = []
        return data
    except Exception:
        return []

def to_unified_schedule(raw_data: Dict[str, Any]) -> Optional[UnifiedSchedule]:
    """Transforms v1 schedule to UnifiedSchedule."""
    try:
        sched_model = TrainSchedule.model_validate(raw_data.get("data", {}))
        
        unified_stations = []
        for stop in sched_model.stops:
            unified_stations.append(UnifiedStation(
                sequence=stop.route_number or 0,
                station_code=stop.station_code or "N/A",
                station_name=stop.station_name or "N/A",
                arrival_time=stop.arrival_time,
                departure_time=stop.departure_time,
                distance_km=float(stop.distance or 0)
            ))
            
        return UnifiedSchedule(
            train_number=sched_model.train_number or "N/A",
            train_name=sched_model.train_name or "N/A",
            schedule=unified_stations,
            data_source="rapidapi"
        )
    except Exception as e:
        logger.error(f"Failed to transform schedule: {e}")
        return None

def to_unified_fare(raw_data: Dict[str, Any], **kwargs) -> Optional[UnifiedFare]:
    """Transforms v2 fare data into UnifiedFare model."""
    try:
        fare_model = Fare.model_validate(raw_data.get("data", {}))
        
        fare_details = []
        for f in fare_model.fares:
            fare_details.append(UnifiedFareInfo(
                class_code=f.class_type or "N/A",
                quota="GN", # Assume GN if not provided by this endpoint
                fare=f.fare or 0.0,
                available_seats=0 # This endpoint usually only provides base fare
            ))
            
        return UnifiedFare(
            train_number=kwargs.get("train_number", "N/A"),
            from_station_code=kwargs.get("from_station_code", "N/A"),
            to_station_code=kwargs.get("to_station_code", "N/A"),
            travel_date=kwargs.get("travel_date", ""),
            fare_details=fare_details,
            data_source="rapidapi"
        )
    except Exception as e:
        logger.error(f"Failed to transform fare: {e}")
        return None

def to_unified_pnr_status(raw_data: Dict[str, Any]) -> Optional[UnifiedPNRStatus]:
    """Transforms v3 PNR status data into UnifiedPNRStatus model."""
    try:
        pnr_model = PNRStatus.model_validate(raw_data.get("data", {}))
        
        # Determine booking status from first passenger if available
        booking_status = "Unknown"
        reservation_status = "Unknown"
        if pnr_model.passengers:
            booking_status = pnr_model.passengers[0].booking_status or "Unknown"
            reservation_status = pnr_model.passengers[0].current_status or "Unknown"
            
        return UnifiedPNRStatus(
            pnr_number=pnr_model.pnr_number or "N/A",
            train_number=pnr_model.train_number or "N/A",
            train_name=pnr_model.train_name or "N/A",
            from_station_code=pnr_model.from_station or "N/A",
            to_station_code=pnr_model.to_station or "N/A",
            travel_date=pnr_model.journey_date or "N/A",
            booking_status=booking_status,
            reservation_status=reservation_status,
            chart_prepared=pnr_model.chart_prepared or False,
            data_source="rapidapi"
        )
    except Exception as e:
        logger.error(f"Failed to transform PNR status: {e}")
        return None
