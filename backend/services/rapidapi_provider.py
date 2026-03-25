import asyncio
import logging
from typing import Optional, Any, Dict

import aiohttp
from pybreaker import CircuitBreaker

from core.providers import ServiceProvider, ServiceStatus
from database.config import Config
from services.multi_layer_cache import multi_layer_cache
from schemas.rapidapi_models import *
from core.container import container

logger = logging.getLogger(__name__)

class RapidApiProvider(ServiceProvider):
    def __init__(self):
        super().__init__("rapidapi")
        self.http_session: Optional[aiohttp.ClientSession] = None
        # Correctly initialize the circuit breaker
        self.breaker = CircuitBreaker(fail_max=5, reset_timeout=60)

    async def init(self):
        """Initializes the shared aiohttp session."""
        headers = {
            "x-rapidapi-key": Config.RAPIDAPI_KEY,
            "x-rapidapi-host": Config.RAPIDAPI_HOST,
            "Content-Type": "application/json",
        }
        self.http_session = aiohttp.ClientSession(headers=headers)
        self.status = ServiceStatus.HEALTHY
        logger.info("✅ RapidAPI Provider Initialized.")

    async def shutdown(self):
        """Closes the shared aiohttp session."""
        if self.http_session and not self.http_session.closed:
            await self.http_session.close()
        self.status = ServiceStatus.FAILED
        logger.info("🔌 RapidAPI Provider Shutdown.")

    @property
    def is_healthy(self) -> bool:
        return self.status == ServiceStatus.HEALTHY and self.http_session and not self.http_session.closed

    async def _execute_request(self, method: str, url: str, params: Optional[Dict]) -> Optional[Dict]:
        """Internal method that executes the HTTP request."""
        async with self.http_session.request(method, url, params=params, timeout=30) as response:
            if response.status != 200:
                try:
                    error_data = await response.json()
                    error_message = error_data.get("message", "No message from API.")
                    logger.error(f"RapidAPI request failed ({response.status}) for {url}: {error_message}")
                except Exception:
                    logger.error(f"RapidAPI request failed ({response.status}) for {url} and error response was not valid JSON.")
                return None
            return await response.json()

    async def _make_request(self, method: str, endpoint: str, params: Optional[Dict] = None) -> Optional[Dict]:
        """
        Makes a request to the RapidAPI endpoint with caching, error handling, and circuit breaking.
        """
        if not self.is_healthy:
            logger.error("RapidAPI Provider is not healthy or session is not initialized.")
            return None

        base_url = f"https://{Config.RAPIDAPI_HOST}"
        full_url = f"{base_url}{endpoint}"
        
        # Caching layer
        cache_key = f"rapidapi:{endpoint}:{frozenset(params.items()) if params else ''}"
        cached_data = await multi_layer_cache.get(cache_key)
        if cached_data:
            logger.debug(f"Cache HIT for {cache_key}")
            return cached_data

        logger.info(f"Calling RapidAPI: {full_url} with params: {params}")
        
        try:
            # Correctly use the circuit breaker with async calls
            data = await self.breaker.call_async(self._execute_request, method, full_url, params)
            if data:
                # Cache the successful response
                await multi_layer_cache.put(cache_key, data, ttl=300)
            return data
        except Exception as e:
            logger.error(f"An unexpected error occurred during RapidAPI request to {full_url}: {e}", exc_info=True)
            return None

    # I will now add the public methods one by one, starting with get_fare.

    async def get_fare(self, train_no: str, from_station_code: str, to_station_code: str) -> Optional[Fare]:
        """Fetches fare from /api/v1/getFare"""
        endpoint = "/api/v1/getFare"
        params = {"trainNo": train_no, "fromStationCode": from_station_code, "toStationCode": to_station_code}
        data = await self._make_request("GET", endpoint, params)
        if data and data.get("status"):
            try:
                # Wrap list in dict if necessary
                fare_data = data["data"]
                if isinstance(fare_data, list):
                    return Fare(data=fare_data, trainNumber=train_no, fromStation=from_station_code, toStation=to_station_code)
                return Fare.parse_obj(fare_data)
            except Exception as e:
                logger.error(f"Failed to parse Fare response: {e}", exc_info=True)
        return None

    async def get_fare_v2(self, train_no: str, from_station_code: str, to_station_code: str) -> Optional[FareV2]:
        """Fetches fare from /api/v2/getFare"""
        endpoint = "/api/v2/getFare"
        params = {"trainNo": train_no, "fromStationCode": from_station_code, "toStationCode": to_station_code}
        data = await self._make_request("GET", endpoint, params)
        if data and data.get("status"):
            try:
                return FareV2.parse_obj(data["data"])
            except Exception as e:
                logger.error(f"Failed to parse FareV2 response: {e}", exc_info=True)
        return None

    async def get_trains_by_station(self, station_code: str) -> Optional[TrainsByStation]:
        """Fetches trains from /api/v3/getTrainsByStation"""
        endpoint = "/api/v3/getTrainsByStation"
        params = {"stationCode": station_code}
        data = await self._make_request("GET", endpoint, params)
        if data and data.get("status"):
            try:
                # Handle cases where data["data"] is a dict with originating/terminating
                station_data = data["data"]
                if isinstance(station_data, dict):
                    return TrainsByStation.parse_obj(station_data)
                return TrainsByStation(data=station_data)
            except Exception as e:
                logger.error(f"Failed to parse TrainsByStation response: {e}", exc_info=True)
        return None

    async def get_live_station(self, station_code: str, hours: int = 1) -> Optional[LiveStation]:
        """
        Fetches live station data (trains expected in the next 'hours') from RapidAPI.
        """
        endpoint = "/api/v3/getLiveStation"
        params = {"stationCode": station_code, "hours": hours}
        
        data = await self._make_request("GET", endpoint, params)
        
        if data and data.get("status"):
            try:
                return LiveStation.parse_obj(data["data"])
            except Exception as e:
                logger.error(f"Failed to parse LiveStation response: {e}", exc_info=True)
                return None
        return None

    async def get_live_train_status(self, train_no: str, start_day: int = 0) -> Optional[LiveTrainStatus]:
        """Fetches live train status from /api/v1/liveTrainStatus"""
        endpoint = "/api/v1/liveTrainStatus"
        params = {"trainNo": train_no, "startDay": start_day}
        data = await self._make_request("GET", endpoint, params)
        if data and data.get("status"):
            try:
                # Handle cases where data is a dict and may have 'data' field
                status_payload = data.get("data", data)
                if isinstance(status_payload, dict) and "success" in status_payload and "data" in status_payload:
                    # Nested data case
                    return LiveTrainStatus.parse_obj(status_payload["data"])
                return LiveTrainStatus.parse_obj(data)
            except Exception as e:
                logger.error(f"Failed to parse LiveTrainStatus response: {e}", exc_info=True)
        return None

    async def get_trains_between_stations(self, from_station_code: str, to_station_code: str) -> Optional[TrainsBetweenStations]:
        """Fetches trains from /api/v2/trainBetweenStations"""
        endpoint = "/api/v2/trainBetweenStations"
        params = {"fromStationCode": from_station_code, "toStationCode": to_station_code}
        data = await self._make_request("GET", endpoint, params)
        if data and data.get("status"):
            try:
                return TrainsBetweenStations.parse_obj(data)
            except Exception as e:
                logger.error(f"Failed to parse TrainsBetweenStations response: {e}", exc_info=True)
        return None

    async def get_trains_between_stations_v3(self, from_station_code: str, to_station_code: str) -> Optional[TrainsBetweenStationsV3]:
        """Fetches trains from /api/v3/trainBetweenStations"""
        endpoint = "/api/v3/trainBetweenStations"
        params = {"fromStationCode": from_station_code, "toStationCode": to_station_code}
        data = await self._make_request("GET", endpoint, params)
        if data and data.get("status"):
            try:
                return TrainsBetweenStationsV3.parse_obj(data)
            except Exception as e:
                logger.error(f"Failed to parse TrainsBetweenStationsV3 response: {e}", exc_info=True)
        return None

    async def get_pnr_status(self, pnr: str) -> Optional[PNRStatus]:
        """Fetches PNR status from /api/v3/getPNRStatus"""
        endpoint = "/api/v3/getPNRStatus"
        params = {"pnrNumber": pnr}
        data = await self._make_request("GET", endpoint, params)
        if data and data.get("status"):
            try:
                return PNRStatus.parse_obj(data["data"])
            except Exception as e:
                logger.error(f"Failed to parse PNRStatus response: {e}", exc_info=True)
        return None

    async def get_pnr_status_v2(self, pnr: str) -> Optional[PNRStatus]:
        """Fetches PNR status from /api/v2/getPNRStatus"""
        endpoint = "/api/v2/getPNRStatus"
        params = {"pnrNumber": pnr}
        data = await self._make_request("GET", endpoint, params)
        # Assuming v2 has similar structure as v3 for basic status
        if data and data.get("status"):
            try:
                return PNRStatus.parse_obj(data["data"])
            except Exception as e:
                logger.error(f"Failed to parse PNRStatus v2 response: {e}", exc_info=True)
        return None

    async def get_pnr_status_detail(self, pnr: str) -> Optional[PNRStatusDetail]:
        """Fetches PNR status detail from /api/v3/getPNRStatusDetail"""
        endpoint = "/api/v3/getPNRStatusDetail"
        params = {"pnrNumber": pnr}
        data = await self._make_request("GET", endpoint, params)
        if data and data.get("status"):
            try:
                return PNRStatusDetail.parse_obj(data["data"])
            except Exception as e:
                logger.error(f"Failed to parse PNRStatusDetail response: {e}", exc_info=True)
        return None

    async def search_station(self, query: str) -> Optional[SearchStation]:
        """Searches for a station from /api/v1/searchStation"""
        endpoint = "/api/v1/searchStation"
        params = {"query": query}
        data = await self._make_request("GET", endpoint, params)
        if data and data.get("status"):
            try:
                return SearchStation.parse_obj(data)
            except Exception as e:
                logger.error(f"Failed to parse SearchStation response: {e}", exc_info=True)
        return None

    async def search_train(self, query: str) -> Optional[SearchTrain]:
        """Searches for a train from /api/v1/searchTrain"""
        endpoint = "/api/v1/searchTrain"
        params = {"query": query}
        data = await self._make_request("GET", endpoint, params)
        if data and data.get("status"):
            try:
                return SearchTrain.parse_obj(data)
            except Exception as e:
                logger.error(f"Failed to parse SearchTrain response: {e}", exc_info=True)
        return None

    async def get_train_schedule(self, train_no: str) -> Optional[TrainSchedule]:
        """Fetches train schedule from /api/v1/getTrainSchedule"""
        endpoint = "/api/v1/getTrainSchedule"
        params = {"trainNo": train_no}
        data = await self._make_request("GET", endpoint, params)
        if data and data.get("status"):
            try:
                return TrainSchedule.parse_obj(data["data"])
            except Exception as e:
                logger.error(f"Failed to parse TrainSchedule response: {e}", exc_info=True)
        return None

    async def get_train_schedule_v2(self, train_no: str) -> Optional[TrainScheduleV2]:
        """Fetches train schedule from /api/v1/getTrainScheduleV2"""
        endpoint = "/api/v1/getTrainScheduleV2"
        params = {"trainNo": train_no}
        data = await self._make_request("GET", endpoint, params)
        if data and data.get("status"):
            try:
                return TrainScheduleV2.parse_obj(data["data"])
            except Exception as e:
                logger.error(f"Failed to parse TrainScheduleV2 response: {e}", exc_info=True)
        return None

    async def check_seat_availability(self, train_no: str, from_station: str, to_station: str, date: str, class_type: str, quota: str) -> Optional[SeatAvailability]:
        """Checks seat availability from /api/v2/checkSeatAvailability"""
        endpoint = "/api/v2/checkSeatAvailability"
        params = {
            "trainNo": train_no,
            "fromStationCode": from_station,
            "toStationCode": to_station,
            "date": date,
            "classType": class_type,
            "quota": quota,
        }
        data = await self._make_request("GET", endpoint, params)
        if data and data.get("status"):
            try:
                return SeatAvailability.parse_obj(data["data"])
            except Exception as e:
                logger.error(f"Failed to parse SeatAvailability response: {e}", exc_info=True)
        return None

    async def check_seat_availability_v1(self, train_no: str, from_station: str, to_station: str, date: str, class_type: str, quota: str) -> Optional[SeatAvailability]:
        """Checks seat availability from /api/v1/checkSeatAvailability"""
        endpoint = "/api/v1/checkSeatAvailability"
        params = {
            "trainNo": train_no,
            "fromStationCode": from_station,
            "toStationCode": to_station,
            "date": date,
            "classType": class_type,
            "quota": quota,
        }
        data = await self._make_request("GET", endpoint, params)
        if data and data.get("status"):
            try:
                avail_data = data["data"]
                if isinstance(avail_data, list):
                    return SeatAvailability(data=avail_data, trainNumber=train_no, trainName="", quota=quota)
                return SeatAvailability.parse_obj(data["data"])
            except Exception as e:
                logger.error(f"Failed to parse SeatAvailability v1 response: {e}", exc_info=True)
        return None

    async def get_train_classes(self, train_no: str) -> Optional[TrainClasses]:
        """Fetches available classes for a given train from RapidAPI."""
        endpoint = "/api/v1/getTrainClasses"
        params = {"trainNo": train_no}
        data = await self._make_request("GET", endpoint, params)
        if data and data.get("status"):
            try:
                classes_data = data["data"]
                if isinstance(classes_data, list):
                    return TrainClasses(data=classes_data)
                return TrainClasses.parse_obj(classes_data)
            except Exception as e:
                logger.error(f"Failed to parse TrainClasses response: {e}", exc_info=True)
        return None

# Global Instance and Container Registration
rapidapi_provider = RapidApiProvider()
container.register(rapidapi_provider)
