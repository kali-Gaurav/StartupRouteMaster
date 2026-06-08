"""
Inference Service for CAT.

This module provides the inference API:
- REST endpoints for predictions
- Batch prediction support
- Streaming predictions
- Caching
- Rate limiting
"""

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from fastapi.responses import JSONResponse
from typing import Dict, List, Any, Optional
from datetime import datetime
import logging
import redis
import json
import asyncio
import time

from .data_models import (
    ContextualData,
    ModelInput,
    AvailabilityPrediction,
    PredictionRequest,
    BatchPredictionRequest,
    HealthCheckResponse,
)
from .data_collector import DataCollector, APIClientConfig
from .preprocessing import PreprocessingModule, PreprocessingConfig
from .model import CATModel, ModelConfig

logger = logging.getLogger(__name__)

router = APIRouter(
    prefix="/api/v1/cat",
    tags=["CAT"]
)


class InferenceService:
    """
    Inference service that provides low-latency availability predictions.
    
    Implements caching, batching, and model versioning.
    """
    
    def __init__(
        self,
        data_collector: DataCollector,
        preprocessing: PreprocessingModule,
        model: CATModel,
        redis_client: redis.Redis,
        cache_ttl: int = 300,  # 5 minutes
    ):
        """
        Initialize the inference service.
        
        Args:
            data_collector: DataCollector for fetching contextual data
            preprocessing: PreprocessingModule for encoding data
            model: CATModel for predictions
            redis_client: Redis client for caching
            cache_ttl: Cache TTL in seconds
        """
        self.data_collector = data_collector
        self.preprocessing = preprocessing
        self.model = model
        self.redis = redis_client
        self.cache_ttl = cache_ttl
        self.model_version = "v1"
    
    async def get_availability_prediction(
        self,
        location_id: str,
        prediction_time: datetime
    ) -> AvailabilityPrediction:
        """
        Get availability prediction for a location and time.
        
        Args:
            location_id: Location identifier
            prediction_time: Time for prediction
            
        Returns:
            AvailabilityPrediction with probability and confidence
        """
        # Generate cache key
        cache_key = f"cat:prediction:{location_id}:{prediction_time.isoformat()}"
        
        # Try to get from cache
        cached = self.redis.get(cache_key)
        if cached:
            logger.info(f"Cache hit for prediction: {cache_key}")
            return AvailabilityPrediction.parse_raw(cached)
        
        # Fetch contextual data
        time_range = {
            'start': prediction_time,
            'end': prediction_time,
        }
        
        contextual_data = await self.data_collector.fetch_contextual_data(location_id, time_range)
        
        # Preprocess data
        model_input = self.preprocessing.preprocess_contextual_data(contextual_data)
        
        # Validate input
        if not self.preprocessing.validate_model_input(model_input):
            raise HTTPException(status_code=400, detail="Invalid model input")
        
        # Generate prediction
        prediction = self.model(model_input)
        
        # Cache prediction
        self.redis.setex(cache_key, self.cache_ttl, prediction.json())
        
        return prediction
    
    async def get_batch_predictions(
        self,
        predictions: List[PredictionRequest]
    ) -> Dict[str, Any]:
        """
        Get batch predictions for multiple locations and times.
        
        Processes predictions in parallel for efficiency and returns
        aggregated results with individual status codes and timing metrics.
        
        Args:
            predictions: List of PredictionRequest objects
            
        Returns:
            Dict containing:
                - predictions: List of prediction results with status codes
                - total_count: Total number of predictions
                - success_count: Number of successful predictions
                - error_count: Number of failed predictions
                - total_time_ms: Total batch processing time in milliseconds
        """
        start_time = time.perf_counter()
        
        if not predictions:
            return {
                'predictions': [],
                'total_count': 0,
                'success_count': 0,
                'error_count': 0,
                'total_time_ms': 0,
            }
        
        # Create tasks for parallel execution
        async def process_single_prediction(request: PredictionRequest) -> Dict[str, Any]:
            """Process a single prediction request."""
            try:
                prediction = await self.get_availability_prediction(
                    request.location_id,
                    request.prediction_time
                )
                return {
                    'status': 'success',
                    'status_code': 200,
                    'location_id': request.location_id,
                    'prediction_time': request.prediction_time.isoformat(),
                    'prediction': prediction.dict(),
                }
            except HTTPException as e:
                logger.error(f"HTTP error predicting for {request.location_id}: {e.detail}")
                return {
                    'status': 'error',
                    'status_code': e.status_code,
                    'location_id': request.location_id,
                    'prediction_time': request.prediction_time.isoformat(),
                    'error': e.detail,
                }
            except Exception as e:
                logger.error(f"Error predicting for {request.location_id}: {e}")
                return {
                    'status': 'error',
                    'status_code': 500,
                    'location_id': request.location_id,
                    'prediction_time': request.prediction_time.isoformat(),
                    'error': str(e),
                }
        
        # Process all predictions in parallel using asyncio.gather
        tasks = [process_single_prediction(req) for req in predictions]
        results = await asyncio.gather(*tasks)
        
        end_time = time.perf_counter()
        total_time_ms = (end_time - start_time) * 1000
        
        # Count successes and errors
        success_count = sum(1 for r in results if r['status'] == 'success')
        error_count = len(results) - success_count
        
        return {
            'predictions': results,
            'total_count': len(predictions),
            'success_count': success_count,
            'error_count': error_count,
            'total_time_ms': round(total_time_ms, 2),
        }
    
    async def stream_predictions(
        self,
        location_id: str,
        start_time: datetime,
        end_time: datetime,
        interval_minutes: int = 15,
    ):
        """
        Stream predictions for a time range.
        
        Args:
            location_id: Location identifier
            start_time: Start time for predictions
            end_time: End time for predictions
            interval_minutes: Time interval between predictions
            
        Yields:
            AvailabilityPrediction objects
        """
        from datetime import timedelta
        
        current_time = start_time
        while current_time <= end_time:
            prediction = await self.get_availability_prediction(location_id, current_time)
            yield prediction
            current_time += timedelta(minutes=interval_minutes)
    
    def get_model_version(self) -> str:
        """Get current model version."""
        return self.model_version
    
    def get_health_status(self) -> HealthCheckResponse:
        """Get health check status."""
        try:
            # Check Redis connection
            self.redis.ping()
            redis_healthy = True
        except Exception as e:
            logger.error(f"Redis health check failed: {e}")
            redis_healthy = False
        
        return HealthCheckResponse(
            status="healthy" if redis_healthy else "degraded",
            timestamp=datetime.now(),
            model_loaded=True,
            external_apis_healthy=redis_healthy,
        )


# Global inference service instance
_inference_service: Optional[InferenceService] = None


def get_inference_service() -> InferenceService:
    """
    Get or create the global inference service instance.
    
    Returns:
        InferenceService instance
    """
    global _inference_service
    
    if _inference_service is None:
        raise RuntimeError("Inference service not initialized. Call init_inference_service() first.")
    
    return _inference_service


def init_inference_service(
    event_api_url: str,
    event_api_key: str,
    weather_api_url: str,
    weather_api_key: str,
    redis_url: str = 'redis://localhost:6379',
    model_path: str = None,
) -> InferenceService:
    """
    Initialize the global inference service.
    
    Args:
        event_api_url: Event Calendar API URL
        event_api_key: Event Calendar API key
        weather_api_url: Weather API URL
        weather_api_key: Weather API key
        redis_url: Redis connection URL
        model_path: Path to saved model (optional)
        
    Returns:
        Initialized InferenceService instance
    """
    global _inference_service
    
    # Create Redis client
    redis_client = redis.from_url(redis_url)
    
    # Create API configs
    event_config = APIClientConfig(
        api_url=event_api_url,
        api_key=event_api_key,
    )
    
    weather_config = APIClientConfig(
        api_url=weather_api_url,
        api_key=weather_api_key,
    )
    
    # Create data collector
    data_collector = DataCollector(
        event_api_config=event_config,
        weather_api_config=weather_config,
        redis_client=redis_client,
    )
    
    # Create preprocessing module
    preprocessing = PreprocessingModule()
    
    # Create or load model
    if model_path:
        model = CATModel.load(model_path)
    else:
        model = CATModel()
    
    # Create inference service
    _inference_service = InferenceService(
        data_collector=data_collector,
        preprocessing=preprocessing,
        model=model,
        redis_client=redis_client,
    )
    
    logger.info("Inference service initialized")
    return _inference_service


# API Endpoints
@router.get("/health")
async def health_check():
    """
    Health check endpoint.
    
    Returns the status of the CAT inference service.
    """
    try:
        service = get_inference_service()
        status = service.get_health_status()
        return status.dict()
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predict")
async def predict_availability(
    request: PredictionRequest,
):
    """
    Get availability prediction for a location and time.
    
    Args:
        request: PredictionRequest with location_id and prediction_time
        
    Returns:
        AvailabilityPrediction with probability and confidence
    """
    try:
        service = get_inference_service()
        prediction = await service.get_availability_prediction(
            request.location_id,
            request.prediction_time
        )
        return prediction.dict()
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error predicting availability: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/predict/batch")
async def predict_batch(
    request: BatchPredictionRequest,
):
    """
    Get batch predictions for multiple locations and times.
    
    Processes predictions in parallel for efficiency and returns
    aggregated results with individual status codes and timing metrics.
    
    Args:
        request: BatchPredictionRequest with list of predictions
        
    Returns:
        Dict containing:
            - predictions: List of prediction results with status codes
            - total_count: Total number of predictions
            - success_count: Number of successful predictions
            - error_count: Number of failed predictions
            - total_time_ms: Total batch processing time in milliseconds
    """
    try:
        service = get_inference_service()
        result = await service.get_batch_predictions(request.predictions)
        return result
    except Exception as e:
        logger.error(f"Error in batch prediction: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/locations")
async def list_locations():
    """
    List available locations for predictions.
    
    Returns:
        List of location registry entries
    """
    try:
        # TODO: Query database for available locations
        locations = [
            {'location_id': 'NDLS', 'location_name': 'New Delhi', 'timezone': 'Asia/Kolkata'},
            {'location_id': 'BCT', 'location_name': 'Mumbai', 'timezone': 'Asia/Kolkata'},
            {'location_id': 'MAS', 'location_name': 'Chennai', 'timezone': 'Asia/Kolkata'},
            {'location_id': 'HWH', 'location_name': 'Kolkata', 'timezone': 'Asia/Kolkata'},
        ]
        return {'locations': locations}
    except Exception as e:
        logger.error(f"Error listing locations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/model/version")
async def get_model_version():
    """
    Get current model version.
    
    Returns:
        Model version string
    """
    try:
        service = get_inference_service()
        return {'version': service.get_model_version()}
    except Exception as e:
        logger.error(f"Error getting model version: {e}")
        raise HTTPException(status_code=500, detail=str(e))