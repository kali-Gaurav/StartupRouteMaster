"""
CAT Client Library for Route Engine Integration.

Provides Python client for CAT inference service with support for
synchronous and asynchronous prediction requests.
"""

import logging
import time
from datetime import datetime
from typing import Optional, List, Dict, Any, Union
from contextlib import contextmanager

import httpx
import asyncio

from ..config import settings
from ..models.schemas import (
    AvailabilityPrediction, PredictionRequest, BatchPredictionRequest,
    BatchPredictionResponse, LocationInfo, LocationListResponse
)

logger = logging.getLogger(__name__)


class CATClientError(Exception):
    """Base exception for CAT client errors."""
    pass


class CATClientTimeoutError(CATClientError):
    """Exception raised when CAT service request times out."""
    pass


class CATClientAuthError(CATClientError):
    """Exception raised when CAT service authentication fails."""
    pass


class CATClient:
    """
    Python client for CAT inference service.
    
    Provides simple API for prediction requests with support for
    both synchronous and asynchronous calls, authentication,
    and error handling.
    """
    
    def __init__(
        self,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        timeout: float = None,
        enable_caching: bool = True
    ):
        """
        Initialize the CAT client.
        
        Args:
            base_url: Base URL of the CAT inference service
            api_key: API key for authentication
            timeout: Request timeout in seconds
            enable_caching: Whether to enable local caching
        """
        self.base_url = base_url or settings.api_url or "http://localhost:8000"
        self.api_key = api_key or settings.api_key
        self.timeout = timeout or 30.0
        self.enable_caching = enable_caching
        
        # Local cache for predictions
        self._cache: Dict[str, AvailabilityPrediction] = {}
        self._cache_ttl = 300  # 5 minutes
        
        # HTTP client
        self._http_client: Optional[httpx.AsyncClient] = None
        self._sync_client: Optional[httpx.Client] = None
    
    async def _get_async_client(self) -> httpx.AsyncClient:
        """Get or create async HTTP client."""
        if self._http_client is None:
            self._http_client = httpx.AsyncClient(
                base_url=self.base_url,
                timeout=self.timeout,
                headers=self._get_auth_headers()
            )
        return self._http_client
    
    def _get_sync_client(self) -> httpx.Client:
        """Get or create sync HTTP client."""
        if self._sync_client is None:
            self._sync_client = httpx.Client(
                base_url=self.base_url,
                timeout=self.timeout,
                headers=self._get_auth_headers()
            )
        return self._sync_client
    
    def _get_auth_headers(self) -> Dict[str, str]:
        """Get authentication headers."""
        headers = {}
        if self.api_key:
            headers["X-API-Key"] = self.api_key
        return headers
    
    def _get_cache_key(self, location_id: str, prediction_time: datetime) -> str:
        """Generate cache key for a prediction request."""
        time_str = prediction_time.isoformat()
        return f"{location_id}:{time_str}"
    
    def _get_cached_prediction(
        self,
        location_id: str,
        prediction_time: datetime
    ) -> Optional[AvailabilityPrediction]:
        """Get cached prediction if valid."""
        if not self.enable_caching:
            return None
        
        cache_key = self._get_cache_key(location_id, prediction_time)
        
        if cache_key in self._cache:
            cached = self._cache[cache_key]
            # Check if cache entry is still valid
            if hasattr(cached, 'prediction_time'):
                # Handle both string and datetime prediction_time
                pred_time = cached.prediction_time
                if isinstance(pred_time, str):
                    pred_time = datetime.fromisoformat(pred_time.replace('Z', '+00:00'))
                if (prediction_time - pred_time).total_seconds() < self._cache_ttl:
                    return cached
        
        return None
    
    def _cache_prediction(
        self,
        location_id: str,
        prediction_time: datetime,
        prediction: AvailabilityPrediction
    ) -> None:
        """Cache a prediction."""
        if not self.enable_caching:
            return
        
        cache_key = self._get_cache_key(location_id, prediction_time)
        self._cache[cache_key] = prediction
    
    def clear_cache(self) -> None:
        """Clear all cached predictions."""
        self._cache.clear()
        logger.debug("CAT client cache cleared")
    
    async def predict(
        self,
        location_id: str,
        prediction_time: datetime,
        context_hours: int = 24
    ) -> AvailabilityPrediction:
        """
        Get availability prediction for a location and time.
        
        Args:
            location_id: Location ID to predict
            prediction_time: Time to predict availability for
            context_hours: Hours of context data to use
            
        Returns:
            AvailabilityPrediction with probability, confidence interval, and factors
            
        Raises:
            CATClientTimeoutError: If request times out
            CATClientAuthError: If authentication fails
            CATClientError: For other errors
        """
        # Check cache first
        cached = self._get_cached_prediction(location_id, prediction_time)
        if cached:
            logger.debug(f"Cache hit for {location_id}")
            return cached
        
        client = await self._get_async_client()
        
        try:
            start_time = time.time()
            
            response = await client.post(
                "/predict",
                json={
                    "location_id": location_id,
                    "prediction_time": prediction_time.isoformat(),
                    "context_hours": context_hours
                }
            )
            
            elapsed_ms = (time.time() - start_time) * 1000
            logger.debug(f"CAT prediction for {location_id} in {elapsed_ms:.1f}ms")
            
            response.raise_for_status()
            
            prediction_data = response.json()
            prediction = AvailabilityPrediction(**prediction_data)
            
            # Cache the prediction
            self._cache_prediction(location_id, prediction_time, prediction)
            
            return prediction
            
        except httpx.TimeoutException as e:
            logger.error(f"CAT prediction request timed out for {location_id}")
            raise CATClientTimeoutError(f"Request timed out: {e}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error(f"CAT authentication failed for {location_id}")
                raise CATClientAuthError(f"Authentication failed: {e}")
            logger.error(f"CAT request failed for {location_id}: {e}")
            raise CATClientError(f"Request failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during CAT prediction for {location_id}: {e}")
            raise CATClientError(f"Unexpected error: {e}")
    
    def predict_sync(
        self,
        location_id: str,
        prediction_time: datetime,
        context_hours: int = 24
    ) -> AvailabilityPrediction:
        """
        Synchronous version of predict().
        
        Args:
            location_id: Location ID to predict
            prediction_time: Time to predict availability for
            context_hours: Hours of context data to use
            
        Returns:
            AvailabilityPrediction with probability, confidence interval, and factors
            
        Raises:
            CATClientTimeoutError: If request times out
            CATClientAuthError: If authentication fails
            CATClientError: For other errors
        """
        # Check cache first
        cached = self._get_cached_prediction(location_id, prediction_time)
        if cached:
            logger.debug(f"Cache hit for {location_id}")
            return cached
        
        client = self._get_sync_client()
        
        try:
            start_time = time.time()
            
            response = client.post(
                "/predict",
                json={
                    "location_id": location_id,
                    "prediction_time": prediction_time.isoformat(),
                    "context_hours": context_hours
                }
            )
            
            elapsed_ms = (time.time() - start_time) * 1000
            logger.debug(f"CAT prediction for {location_id} in {elapsed_ms:.1f}ms")
            
            response.raise_for_status()
            
            prediction_data = response.json()
            prediction = AvailabilityPrediction(**prediction_data)
            
            # Cache the prediction
            self._cache_prediction(location_id, prediction_time, prediction)
            
            return prediction
            
        except httpx.TimeoutException as e:
            logger.error(f"CAT prediction request timed out for {location_id}")
            raise CATClientTimeoutError(f"Request timed out: {e}")
        except httpx.HTTPStatusError as e:
            if e.response.status_code == 401:
                logger.error(f"CAT authentication failed for {location_id}")
                raise CATClientAuthError(f"Authentication failed: {e}")
            logger.error(f"CAT request failed for {location_id}: {e}")
            raise CATClientError(f"Request failed: {e}")
        except Exception as e:
            logger.error(f"Unexpected error during CAT prediction for {location_id}: {e}")
            raise CATClientError(f"Unexpected error: {e}")
    
    async def predict_batch(
        self,
        predictions: List[Dict[str, Any]]
    ) -> List[AvailabilityPrediction]:
        """
        Get batch predictions for multiple locations and times.
        
        Args:
            predictions: List of prediction requests, each with:
                - location_id: Location ID to predict
                - prediction_time: Time to predict
                - context_hours: Optional, hours of context data
                
        Returns:
            List of AvailabilityPrediction objects
        """
        client = await self._get_async_client()
        
        try:
            # Prepare batch request
            batch_predictions = []
            for pred in predictions:
                batch_predictions.append({
                    "location_id": pred["location_id"],
                    "prediction_time": pred["prediction_time"].isoformat() if isinstance(pred["prediction_time"], datetime) else pred["prediction_time"],
                    "context_hours": pred.get("context_hours", 24)
                })
            
            response = await client.post(
                "/predict/batch",
                json={"predictions": batch_predictions}
            )
            
            response.raise_for_status()
            
            response_data = response.json()
            batch_response = BatchPredictionResponse(**response_data)
            
            # Cache all predictions
            for pred in batch_response.predictions:
                pred_time = datetime.fromisoformat(pred.prediction_time.replace('Z', '+00:00'))
                self._cache_prediction(pred.location_id, pred_time, pred)
            
            return batch_response.predictions
            
        except Exception as e:
            logger.error(f"Batch prediction failed: {e}")
            raise CATClientError(f"Batch prediction failed: {e}")
    
    async def get_locations(self) -> List[LocationInfo]:
        """
        Get list of available locations.
        
        Returns:
            List of LocationInfo objects
        """
        client = await self._get_async_client()
        
        try:
            response = await client.get("/locations")
            response.raise_for_status()
            
            response_data = response.json()
            location_list = LocationListResponse(**response_data)
            
            return location_list.locations
            
        except Exception as e:
            logger.error(f"Failed to get locations: {e}")
            raise CATClientError(f"Failed to get locations: {e}")
    
    async def health_check(self) -> Dict[str, Any]:
        """
        Check CAT service health.
        
        Returns:
            Health status information
        """
        client = await self._get_async_client()
        
        try:
            response = await client.get("/health")
            response.raise_for_status()
            
            return response.json()
            
        except Exception as e:
            logger.error(f"Health check failed: {e}")
            raise CATClientError(f"Health check failed: {e}")
    
    async def close(self) -> None:
        """Close HTTP clients and clean up resources."""
        if self._http_client:
            await self._http_client.aclose()
            self._http_client = None
        
        if self._sync_client:
            self._sync_client.close()
            self._sync_client = None
        
        logger.debug("CAT client closed")
    
    @contextmanager
    def session(self):
        """Context manager for client session."""
        try:
            yield self
        finally:
            # For async, we need to close explicitly
            pass


def create_cat_client(
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    timeout: float = None,
    enable_caching: bool = True
) -> CATClient:
    """
    Factory function to create a CAT client.
    
    Args:
        base_url: Base URL of the CAT inference service
        api_key: API key for authentication
        timeout: Request timeout in seconds
        enable_caching: Whether to enable local caching
        
    Returns:
        Configured CATClient instance
    """
    return CATClient(
        base_url=base_url,
        api_key=api_key,
        timeout=timeout,
        enable_caching=enable_caching
    )
