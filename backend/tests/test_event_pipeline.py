#!/usr/bin/env python3
"""
Test script for minimal Kafka event backbone

Phase 4 - Step 1: Test the 3-event pipeline
"""

import asyncio
import logging
import os
import sys
from datetime import datetime

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Enable events for testing
os.environ['KAFKA_ENABLE_EVENTS'] = 'true'
os.environ['KAFKA_BOOTSTRAP_SERVERS'] = 'localhost:9092'

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Force reload config after setting env vars
import importlib
import backend.config
importlib.reload(backend.config)
from config import Config

# Also reload the consumer module to pick up new config
import backend.services.analytics_consumer
importlib.reload(backend.services.analytics_consumer)
from services.analytics_consumer import get_analytics_consumer, start_analytics_consumer

from services.event_producer import (
    get_event_producer,
    publish_route_searched,
    publish_booking_created,
    publish_train_delayed
)
from services.delay_service import delay_service

logger.info(f"KAFKA_ENABLE_EVENTS: {Config.KAFKA_ENABLE_EVENTS}")
logger.info(f"KAFKA_BOOTSTRAP_SERVERS: {Config.KAFKA_BOOTSTRAP_SERVERS}")

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_event_pipeline():
    """Test the complete event pipeline"""
    logger.info("Starting event pipeline test...")

    # Start analytics consumer in background
    consumer_task = asyncio.create_task(start_analytics_consumer())
    await asyncio.sleep(2)  # Let consumer start

    try:
        # Test 1: Route search event
        logger.info("Testing route search event...")
        success = await publish_route_searched(
            user_id="test_user_123",
            source="NDLS",
            destination="BCT",
            travel_date="2024-01-15",
            routes_shown=3,
            search_latency_ms=245.67,
            filters={"class": "3A", "max_transfers": 2}
        )
        logger.info(f"Route search event published: {success}")

        # Test 2: Booking creation event
        logger.info("Testing booking creation event...")
        success = await publish_booking_created(
            user_id="test_user_123",
            route_id="route_456",
            total_cost=1250.50,
            segments=[
                {"train": "12951", "from": "NDLS", "to": "BCT", "departure": "2024-01-15T10:00:00"},
            ],
            booking_reference="BK123456789"
        )
        logger.info(f"Booking creation event published: {success}")

        # Test 3: Train delay event via delay service
        logger.info("Testing train delay event...")
        delay_report = await delay_service.report_train_delay(
            train_id="12951",
            delay_minutes=30,
            station_code="NDLS",
            scheduled_departure="2024-01-15T10:00:00",
            estimated_departure="2024-01-15T10:30:00",
            reason="Signal failure"
        )
        logger.info(f"Train delay reported: {delay_report}")

        # Wait for events to be processed
        await asyncio.sleep(3)

        # Check consumer stats
        consumer = get_analytics_consumer()
        stats = consumer.get_stats()
        logger.info(f"Consumer stats: {stats}")

        # Test in-memory fallback if Kafka fails
        producer = get_event_producer()
        if hasattr(producer, 'get_events'):
            # In-memory producer
            route_events = producer.get_events('route_events')
            booking_events = producer.get_events('booking_events')
            delay_events = producer.get_events('delay_events')

            logger.info(f"In-memory events - Route: {len(route_events)}, Booking: {len(booking_events)}, Delay: {len(delay_events)}")

        logger.info("Event pipeline test completed successfully!")

    except Exception as e:
        logger.error(f"Test failed: {e}")
        raise
    finally:
        # Cleanup
        consumer = get_analytics_consumer()
        await consumer.stop()

        producer = get_event_producer()
        await producer.close()

        consumer_task.cancel()
        try:
            await consumer_task
        except asyncio.CancelledError:
            pass

if __name__ == "__main__":
    asyncio.run(test_event_pipeline())
