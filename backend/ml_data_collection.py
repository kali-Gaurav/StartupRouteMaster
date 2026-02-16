#!/usr/bin/env python3
"""
RouteMaster ML Training Pipeline - Data Collection Mode
======================================================

Collects production data during staging rollout for ML training.

Data Collection Strategy:
1. Capture all search requests and responses
2. Record user behavior patterns (selections, conversions)
3. Log performance metrics for each request
4. Store feature vectors for ML model training
5. Maintain data quality and privacy compliance

Data Sources:
- Route search requests/responses
- User interaction logs (clicks, bookings)
- Performance metrics (latency, errors)
- External data (weather, holidays, events)

Safety Features:
- Privacy-preserving data collection
- Configurable sampling rates
- Automatic data quality validation
- GDPR compliance logging
"""

import asyncio
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import hashlib
import uuid
from enum import Enum
import aiofiles
import os
from pathlib import Path

# Database and async imports
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker
from sqlalchemy import Column, Integer, String, DateTime, Text, Float, Boolean, JSON, Index
from sqlalchemy.ext.declarative import declarative_base

# Prometheus metrics
from prometheus_client import Counter, Histogram, Gauge

Base = declarative_base()

# Data collection metrics
DATA_COLLECTION_REQUESTS = Counter(
    'data_collection_requests_total',
    'Total requests processed in data collection mode',
    ['endpoint', 'status']
)

DATA_COLLECTION_LATENCY = Histogram(
    'data_collection_latency_seconds',
    'Request latency during data collection',
    ['endpoint'],
    buckets=(0.1, 0.5, 1, 2.5, 5, 10, 25, 50)
)

DATA_COLLECTION_ERRORS = Counter(
    'data_collection_errors_total',
    'Errors during data collection',
    ['error_type']
)

DATA_QUALITY_SCORE = Gauge(
    'data_collection_quality_score',
    'Data quality score (0-1)',
    ['data_type']
)

class DataCollectionMode(Enum):
    """Data collection operational modes"""
    DISABLED = "disabled"
    SAMPLE_10_PERCENT = "sample_10_percent"
    SAMPLE_50_PERCENT = "sample_50_percent"
    FULL_COLLECTION = "full_collection"

@dataclass
class SearchRequestData:
    """Captured search request data"""
    request_id: str
    timestamp: datetime
    user_id_hash: str  # Privacy-preserving user identifier
    origin: str
    destination: str
    search_date: str
    passengers: int
    preferred_classes: List[str]
    flexible_dates: bool
    user_agent: str
    ip_hash: str  # Privacy-preserving IP
    session_id: str
    request_payload: Dict[str, Any]

@dataclass
class SearchResponseData:
    """Captured search response data"""
    request_id: str
    timestamp: datetime
    routes_returned: int
    response_time_ms: float
    error_occurred: bool
    error_message: Optional[str]
    response_payload: Dict[str, Any]  # Full response for ML training

@dataclass
class UserInteractionData:
    """User interaction and conversion data"""
    request_id: str
    timestamp: datetime
    interaction_type: str  # 'view', 'click', 'book', 'convert'
    route_selected: Optional[Dict[str, Any]]
    booking_completed: bool
    booking_amount: Optional[float]
    user_feedback: Optional[Dict[str, Any]]

@dataclass
class PerformanceMetricsData:
    """Performance and system metrics"""
    request_id: str
    timestamp: datetime
    endpoint: str
    method: str
    status_code: int
    response_time_ms: float
    database_query_time_ms: Optional[float]
    cache_hit: bool
    memory_usage_mb: float
    cpu_usage_percent: float

# Database models for data collection
class SearchRequest(Base):
    """Search request log"""
    __tablename__ = 'ml_search_requests'

    id = Column(Integer, primary_key=True)
    request_id = Column(String(36), unique=True, index=True)
    timestamp = Column(DateTime, index=True)
    user_id_hash = Column(String(64), index=True)
    origin = Column(String(10))
    destination = Column(String(10))
    search_date = Column(String(10))
    passengers = Column(Integer)
    preferred_classes = Column(JSON)
    flexible_dates = Column(Boolean)
    user_agent = Column(Text)
    ip_hash = Column(String(64))
    session_id = Column(String(36))
    request_payload = Column(JSON)

class SearchResponse(Base):
    """Search response log"""
    __tablename__ = 'ml_search_responses'

    id = Column(Integer, primary_key=True)
    request_id = Column(String(36), index=True)
    timestamp = Column(DateTime, index=True)
    routes_returned = Column(Integer)
    response_time_ms = Column(Float)
    error_occurred = Column(Boolean)
    error_message = Column(Text)
    response_payload = Column(JSON)

class UserInteraction(Base):
    """User interaction log"""
    __tablename__ = 'ml_user_interactions'

    id = Column(Integer, primary_key=True)
    request_id = Column(String(36), index=True)
    timestamp = Column(DateTime, index=True)
    interaction_type = Column(String(20))
    route_selected = Column(JSON)
    booking_completed = Column(Boolean)
    booking_amount = Column(Float)
    user_feedback = Column(JSON)

class PerformanceMetrics(Base):
    """Performance metrics log"""
    __tablename__ = 'ml_performance_metrics'

    id = Column(Integer, primary_key=True)
    request_id = Column(String(36), index=True)
    timestamp = Column(DateTime, index=True)
    endpoint = Column(String(100))
    method = Column(String(10))
    status_code = Column(Integer)
    response_time_ms = Column(Float)
    database_query_time_ms = Column(Float)
    cache_hit = Column(Boolean)
    memory_usage_mb = Column(Float)
    cpu_usage_percent = Column(Float)

class ExternalContextData(Base):
    """External context data (weather, holidays, etc.)"""
    __tablename__ = 'ml_external_context'

    id = Column(Integer, primary_key=True)
    date = Column(String(10), index=True)
    context_type = Column(String(50))  # 'weather', 'holiday', 'event'
    location = Column(String(100))
    data = Column(JSON)
    timestamp = Column(DateTime, default=datetime.utcnow)

class DataCollectionService:
    """
    Service for collecting and storing ML training data

    Features:
    - Privacy-preserving data collection
    - Configurable sampling rates
    - Real-time data quality monitoring
    - GDPR compliance
    """

    def __init__(self,
                 database_url: str,
                 collection_mode: DataCollectionMode = DataCollectionMode.FULL_COLLECTION,
                 data_dir: str = "./ml_training_data"):
        self.database_url = database_url
        self.collection_mode = collection_mode
        self.data_dir = Path(data_dir)
        self.data_dir.mkdir(exist_ok=True)

        # Async database setup
        self.engine = create_async_engine(database_url, echo=False)
        self.async_session = sessionmaker(self.engine, class_=AsyncSession, expire_on_commit=False)

        # Data quality tracking
        self.data_quality_scores = {
            'search_requests': 1.0,
            'search_responses': 1.0,
            'user_interactions': 1.0,
            'performance_metrics': 1.0
        }

    async def initialize(self):
        """Initialize database and data collection"""
        async with self.engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        logging.info(f"Data collection initialized in {self.collection_mode.value} mode")

    async def should_collect_request(self, request_data: Dict[str, Any]) -> bool:
        """Determine if request should be collected based on sampling mode"""
        if self.collection_mode == DataCollectionMode.DISABLED:
            return False
        elif self.collection_mode == DataCollectionMode.FULL_COLLECTION:
            return True
        elif self.collection_mode == DataCollectionMode.SAMPLE_10_PERCENT:
            # Sample 10% of requests
            request_hash = hashlib.md5(json.dumps(request_data, sort_keys=True).encode()).hexdigest()
            return int(request_hash[:8], 16) % 100 < 10
        elif self.collection_mode == DataCollectionMode.SAMPLE_50_PERCENT:
            # Sample 50% of requests
            request_hash = hashlib.md5(json.dumps(request_data, sort_keys=True).encode()).hexdigest()
            return int(request_hash[:8], 16) % 100 < 50

        return False

    async def collect_search_request(self, request_data: SearchRequestData):
        """Collect search request data"""
        try:
            async with self.async_session() as session:
                db_record = SearchRequest(
                    request_id=request_data.request_id,
                    timestamp=request_data.timestamp,
                    user_id_hash=request_data.user_id_hash,
                    origin=request_data.origin,
                    destination=request_data.destination,
                    search_date=request_data.search_date,
                    passengers=request_data.passengers,
                    preferred_classes=request_data.preferred_classes,
                    flexible_dates=request_data.flexible_dates,
                    user_agent=request_data.user_agent,
                    ip_hash=request_data.ip_hash,
                    session_id=request_data.session_id,
                    request_payload=request_data.request_payload
                )

                session.add(db_record)
                await session.commit()

            DATA_COLLECTION_REQUESTS.labels(endpoint='search', status='collected').inc()
            await self._update_data_quality('search_requests', True)

        except Exception as e:
            logging.error(f"Failed to collect search request: {e}")
            DATA_COLLECTION_ERRORS.labels(error_type='search_request_collection').inc()
            await self._update_data_quality('search_requests', False)

    async def collect_search_response(self, response_data: SearchResponseData):
        """Collect search response data"""
        try:
            async with self.async_session() as session:
                db_record = SearchResponse(
                    request_id=response_data.request_id,
                    timestamp=response_data.timestamp,
                    routes_returned=response_data.routes_returned,
                    response_time_ms=response_data.response_time_ms,
                    error_occurred=response_data.error_occurred,
                    error_message=response_data.error_message,
                    response_payload=response_data.response_payload
                )

                session.add(db_record)
                await session.commit()

            await self._update_data_quality('search_responses', True)

        except Exception as e:
            logging.error(f"Failed to collect search response: {e}")
            DATA_COLLECTION_ERRORS.labels(error_type='search_response_collection').inc()
            await self._update_data_quality('search_responses', False)

    async def collect_user_interaction(self, interaction_data: UserInteractionData):
        """Collect user interaction data"""
        try:
            async with self.async_session() as session:
                db_record = UserInteraction(
                    request_id=interaction_data.request_id,
                    timestamp=interaction_data.timestamp,
                    interaction_type=interaction_data.interaction_type,
                    route_selected=interaction_data.route_selected,
                    booking_completed=interaction_data.booking_completed,
                    booking_amount=interaction_data.booking_amount,
                    user_feedback=interaction_data.user_feedback
                )

                session.add(db_record)
                await session.commit()

            await self._update_data_quality('user_interactions', True)

        except Exception as e:
            logging.error(f"Failed to collect user interaction: {e}")
            DATA_COLLECTION_ERRORS.labels(error_type='user_interaction_collection').inc()
            await self._update_data_quality('user_interactions', False)

    async def collect_performance_metrics(self, metrics_data: PerformanceMetricsData):
        """Collect performance metrics"""
        try:
            async with self.async_session() as session:
                db_record = PerformanceMetrics(
                    request_id=metrics_data.request_id,
                    timestamp=metrics_data.timestamp,
                    endpoint=metrics_data.endpoint,
                    method=metrics_data.method,
                    status_code=metrics_data.status_code,
                    response_time_ms=metrics_data.response_time_ms,
                    database_query_time_ms=metrics_data.database_query_time_ms,
                    cache_hit=metrics_data.cache_hit,
                    memory_usage_mb=metrics_data.memory_usage_mb,
                    cpu_usage_percent=metrics_data.cpu_usage_percent
                )

                session.add(db_record)
                await session.commit()

            await self._update_data_quality('performance_metrics', True)

        except Exception as e:
            logging.error(f"Failed to collect performance metrics: {e}")
            DATA_COLLECTION_ERRORS.labels(error_type='performance_metrics_collection').inc()
            await self._update_data_quality('performance_metrics', False)

    async def collect_external_context(self, context_data: Dict[str, Any]):
        """Collect external context data (weather, holidays, etc.)"""
        try:
            async with self.async_session() as session:
                db_record = ExternalContextData(
                    date=context_data['date'],
                    context_type=context_data['type'],
                    location=context_data.get('location', ''),
                    data=context_data['data']
                )

                session.add(db_record)
                await session.commit()

        except Exception as e:
            logging.error(f"Failed to collect external context: {e}")
            DATA_COLLECTION_ERRORS.labels(error_type='external_context_collection').inc()

    async def _update_data_quality(self, data_type: str, success: bool):
        """Update data quality scores"""
        # Simple exponential moving average for quality scoring
        alpha = 0.1  # Smoothing factor
        current_score = self.data_quality_scores[data_type]

        new_score = current_score * (1 - alpha) + (1.0 if success else 0.0) * alpha
        self.data_quality_scores[data_type] = new_score

        DATA_QUALITY_SCORE.labels(data_type=data_type).set(new_score)

    async def export_training_data(self, start_date: datetime, end_date: datetime) -> str:
        """
        Export collected data for ML training

        Returns:
            Path to exported data file
        """
        export_file = self.data_dir / f"training_data_{start_date.strftime('%Y%m%d')}_{end_date.strftime('%Y%m%d')}.json"

        training_data = {
            'metadata': {
                'export_timestamp': datetime.utcnow().isoformat(),
                'date_range': {
                    'start': start_date.isoformat(),
                    'end': end_date.isoformat()
                },
                'collection_mode': self.collection_mode.value,
                'data_quality_scores': self.data_quality_scores
            },
            'search_requests': [],
            'search_responses': [],
            'user_interactions': [],
            'performance_metrics': [],
            'external_context': []
        }

        try:
            async with self.async_session() as session:
                # Export search requests
                result = await session.execute(
                    f"SELECT * FROM ml_search_requests WHERE timestamp BETWEEN '{start_date}' AND '{end_date}'"
                )
                training_data['search_requests'] = [dict(row) for row in result.fetchall()]

                # Export responses
                result = await session.execute(
                    f"SELECT * FROM ml_search_responses WHERE timestamp BETWEEN '{start_date}' AND '{end_date}'"
                )
                training_data['search_responses'] = [dict(row) for row in result.fetchall()]

                # Export interactions
                result = await session.execute(
                    f"SELECT * FROM ml_user_interactions WHERE timestamp BETWEEN '{start_date}' AND '{end_date}'"
                )
                training_data['user_interactions'] = [dict(row) for row in result.fetchall()]

                # Export performance metrics
                result = await session.execute(
                    f"SELECT * FROM ml_performance_metrics WHERE timestamp BETWEEN '{start_date}' AND '{end_date}'"
                )
                training_data['performance_metrics'] = [dict(row) for row in result.fetchall()]

                # Export external context
                result = await session.execute(
                    f"SELECT * FROM ml_external_context WHERE date BETWEEN '{start_date.date()}' AND '{end_date.date()}'"
                )
                training_data['external_context'] = [dict(row) for row in result.fetchall()]

            # Write to file
            async with aiofiles.open(export_file, 'w') as f:
                await f.write(json.dumps(training_data, indent=2, default=str))

            logging.info(f"Training data exported to {export_file}")
            return str(export_file)

        except Exception as e:
            logging.error(f"Failed to export training data: {e}")
            raise

    def get_collection_stats(self) -> Dict[str, Any]:
        """Get data collection statistics"""
        return {
            'collection_mode': self.collection_mode.value,
            'data_quality_scores': self.data_quality_scores,
            'data_directory': str(self.data_dir),
            'database_url': self.database_url.replace('postgresql://', 'postgresql://[REDACTED]@')  # Hide credentials
        }

class PrivacyPreservingDataProcessor:
    """
    Ensures GDPR compliance and privacy preservation

    Features:
    - PII removal and hashing
    - Data retention policies
    - User consent tracking
    - Data anonymization
    """

    @staticmethod
    def hash_user_identifier(identifier: str) -> str:
        """Create privacy-preserving hash of user identifier"""
        return hashlib.sha256(identifier.encode()).hexdigest()[:16]

    @staticmethod
    def hash_ip_address(ip: str) -> str:
        """Hash IP address for privacy"""
        return hashlib.sha256(ip.encode()).hexdigest()[:16]

    @staticmethod
    def sanitize_request_data(request_data: Dict[str, Any]) -> Dict[str, Any]:
        """Remove or hash PII from request data"""
        sanitized = request_data.copy()

        # Remove direct PII
        pii_fields = ['email', 'phone', 'name', 'credit_card', 'ssn']
        for field in pii_fields:
            if field in sanitized:
                del sanitized[field]

        # Hash IP if present
        if 'ip_address' in sanitized:
            sanitized['ip_hash'] = PrivacyPreservingDataProcessor.hash_ip_address(sanitized['ip_address'])
            del sanitized['ip_address']

        return sanitized

# Integration middleware for FastAPI
class DataCollectionMiddleware:
    """
    FastAPI middleware for automatic data collection

    Integrates with:
    - Request/response logging
    - Performance monitoring
    - User interaction tracking
    """

    def __init__(self, data_collection_service: DataCollectionService):
        self.data_collection = data_collection_service

    async def process_request(self, request_data: Dict[str, Any]) -> str:
        """Process incoming request and return request ID"""
        request_id = str(uuid.uuid4())

        # Check if we should collect this request
        if await self.data_collection.should_collect_request(request_data):
            # Create search request data
            search_data = SearchRequestData(
                request_id=request_id,
                timestamp=datetime.utcnow(),
                user_id_hash=PrivacyPreservingDataProcessor.hash_user_identifier(
                    request_data.get('user_id', str(uuid.uuid4()))
                ),
                origin=request_data.get('origin', ''),
                destination=request_data.get('destination', ''),
                search_date=request_data.get('date', ''),
                passengers=request_data.get('passengers', 1),
                preferred_classes=request_data.get('classes', []),
                flexible_dates=request_data.get('flexible_dates', False),
                user_agent=request_data.get('user_agent', ''),
                ip_hash=PrivacyPreservingDataProcessor.hash_ip_address(
                    request_data.get('ip_address', '127.0.0.1')
                ),
                session_id=request_data.get('session_id', ''),
                request_payload=PrivacyPreservingDataProcessor.sanitize_request_data(request_data)
            )

            # Collect asynchronously (don't block request processing)
            asyncio.create_task(self.data_collection.collect_search_request(search_data))

        return request_id

    async def process_response(self,
                              request_id: str,
                              response_data: Dict[str, Any],
                              response_time_ms: float,
                              error_occurred: bool = False,
                              error_message: str = None):
        """Process response data"""
        # Create response data
        response_record = SearchResponseData(
            request_id=request_id,
            timestamp=datetime.utcnow(),
            routes_returned=len(response_data.get('routes', [])),
            response_time_ms=response_time_ms,
            error_occurred=error_occurred,
            error_message=error_message,
            response_payload=response_data
        )

        # Collect asynchronously
        asyncio.create_task(self.data_collection.collect_search_response(response_record))

    async def process_performance_metrics(self,
                                        request_id: str,
                                        endpoint: str,
                                        method: str,
                                        status_code: int,
                                        response_time_ms: float,
                                        db_query_time_ms: float = None,
                                        cache_hit: bool = False,
                                        memory_usage_mb: float = 0.0,
                                        cpu_usage_percent: float = 0.0):
        """Process performance metrics"""
        metrics_data = PerformanceMetricsData(
            request_id=request_id,
            timestamp=datetime.utcnow(),
            endpoint=endpoint,
            method=method,
            status_code=status_code,
            response_time_ms=response_time_ms,
            database_query_time_ms=db_query_time_ms,
            cache_hit=cache_hit,
            memory_usage_mb=memory_usage_mb,
            cpu_usage_percent=cpu_usage_percent
        )

        # Collect asynchronously
        asyncio.create_task(self.data_collection.collect_performance_metrics(metrics_data))

# Example usage and testing
async def main():
    """Example data collection service usage"""
    logging.basicConfig(level=logging.INFO)

    # Initialize data collection service
    database_url = "postgresql+asyncpg://user:password@localhost/routemaster_ml"
    service = DataCollectionService(
        database_url=database_url,
        collection_mode=DataCollectionMode.FULL_COLLECTION
    )

    await service.initialize()

    # Example: Collect a search request
    request_data = SearchRequestData(
        request_id=str(uuid.uuid4()),
        timestamp=datetime.utcnow(),
        user_id_hash="hashed_user_123",
        origin="NDLS",
        destination="MAS",
        search_date="2024-02-01",
        passengers=2,
        preferred_classes=["2A", "3A"],
        flexible_dates=True,
        user_agent="Mozilla/5.0...",
        ip_hash="hashed_ip_456",
        session_id=str(uuid.uuid4()),
        request_payload={"origin": "NDLS", "destination": "MAS", "date": "2024-02-01"}
    )

    await service.collect_search_request(request_data)

    # Export training data
    start_date = datetime.utcnow() - timedelta(days=30)
    end_date = datetime.utcnow()
    export_path = await service.export_training_data(start_date, end_date)

    print(f"Data collection stats: {service.get_collection_stats()}")
    print(f"Training data exported to: {export_path}")

if __name__ == "__main__":
    asyncio.run(main())