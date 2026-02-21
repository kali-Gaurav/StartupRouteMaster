#!/usr/bin/env python3
"""
Simple Load Test for Minimal Event Backbone

Phase 4 - Stage 1: Local Integration Test
"""

import asyncio
import logging
import os
import sys
import time
import psutil

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Enable events for testing
os.environ['KAFKA_ENABLE_EVENTS'] = 'true'
# Use real Kafka broker for success path testing
os.environ['KAFKA_BOOTSTRAP_SERVERS'] = 'localhost:9092'

from backend.services.event_producer import get_event_producer, KafkaEventProducer, publish_route_searched, publish_booking_created, publish_train_delayed, _event_producer
from backend.services.analytics_consumer import start_analytics_consumer, get_analytics_consumer

logging.basicConfig(level=logging.WARNING)  # Reduce log noise
logger = logging.getLogger(__name__)

async def run_load_test():
    """Run load test with 1000 route searches, 200 bookings, 50 delays"""
    print("🚀 EVENT BACKBONE LOAD TEST")
    print("Target: 1000 searches + 200 bookings + 50 delays")
    print()

    start_time = time.time()
    errors = 0
    operations = 0

    # Start consumer
    consumer_task = asyncio.create_task(start_analytics_consumer())
    await asyncio.sleep(2)

    # Check producer
    _event_producer = None  # Reset for fresh test
    producer = get_event_producer()
    print(f"Using producer: {type(producer).__name__}")
    if hasattr(producer, 'reset_circuit_breaker'):
        producer.reset_circuit_breaker()
        print("Circuit breaker reset for test")

    # Wait for producer to be ready
    await asyncio.sleep(5)

    try:
        # Route searches
        print("📍 Publishing route search events...")
        for i in range(1000):
            try:
                result = await publish_route_searched(
                    user_id=f"user_{i%100}",
                    source="NDLS",
                    destination="BCT",
                    travel_date="2024-01-15",
                    routes_shown=i%10+1,
                    search_latency_ms=i%50+10
                )
                if result:
                    operations += 1
                else:
                    errors += 1
                    if errors < 5:  # Print first few errors
                        print(f"Failed to publish route search {i}")
            except Exception as e:
                errors += 1
                if errors < 5:
                    print(f"Exception publishing route search {i}: {e}")

        # Bookings
        print("🎫 Publishing booking events...")
        for i in range(200):
            try:
                await publish_booking_created(
                    user_id=f"user_{i%50}",
                    route_id=f"route_{i%20}",
                    total_cost=i%5000+500,
                    segments=[{"train": f"TRAIN{i%100:03d}"}],
                    booking_reference=f"BK{i:06d}"
                )
                operations += 1
            except Exception as e:
                errors += 1

        # Delays
        print("⏰ Publishing delay events...")
        for i in range(50):
            try:
                await publish_train_delayed(
                    train_id=f"TRAIN{i%200:03d}",
                    delay_minutes=i%120+5,
                    station_code="NDLS",
                    scheduled_departure="2024-01-15T10:00:00",
                    estimated_departure="2024-01-15T11:00:00"
                )
                operations += 1
            except Exception as e:
                errors += 1

        # Wait for processing
        await asyncio.sleep(3)

        # Results
        end_time = time.time()
        duration = end_time - start_time

        cpu_max = psutil.cpu_percent(interval=1)
        mem_max = psutil.virtual_memory().percent

        consumer = get_analytics_consumer()
        consumer_stats = consumer.get_stats()

        # Get producer metrics
        producer = get_event_producer()
        producer_metrics = producer.get_metrics() if hasattr(producer, 'get_metrics') else {}

        print("\n📊 RESULTS")
        print(f"Duration: {duration:.1f}s")
        print(f"Operations: {operations}")
        print(f"Errors: {errors}")
        print(f"Ops/sec: {operations/duration:.1f}")
        print(f"Max CPU: {cpu_max:.1f}%")
        print(f"Max Memory: {mem_max:.1f}%")
        print(f"Events processed: {consumer_stats.get('event_counts', {})}")
        print(f"Consumer lag estimate: {consumer_stats.get('consumer_lag_estimate_seconds', 0):.1f}s")

        # Producer metrics
        if producer_metrics:
            success_rate = (producer_metrics.get('publish_successes', 0) / producer_metrics.get('publish_attempts', 1)) * 100
            p95_latency = producer_metrics.get('send_p95_latency_ms', 0)
            circuit_opens = producer_metrics.get('circuit_breaker_opens', 0)
            print(f"Producer success rate: {success_rate:.1f}%")
            print(f"Producer P95 latency: {p95_latency:.1f}ms")
            print(f"Circuit breaker opens: {circuit_opens}")
            print(f"Producer failures: {producer_metrics.get('publish_failures', 0)}")

        # Evaluation - focus on Kafka success path metrics
        success = (
            errors/operations < 0.01 and  # <1% error rate
            cpu_max < 90 and              # CPU reasonable (relaxed)
            consumer_stats.get('is_running', False) and  # Consumer active
            producer_metrics.get('circuit_breaker_opens', 0) == 0 and  # No circuit breaker activation
            producer_metrics.get('send_p95_latency_ms', 1000) < 100 and  # P95 < 100ms
            producer_metrics.get('publish_successes', 0) == operations  # All publishes successful
        )

        print("\n🎯 EVALUATION")
        if success:
            print("✅ KAFKA SUCCESS PATH TEST PASSED")
            print("✅ Events handle load with real broker")
            print("✅ No circuit breaker activation")
            print("✅ Low latency and high success rate")
            print("✅ READY FOR STAGING ENABLEMENT")
        else:
            print("❌ KAFKA SUCCESS PATH TEST FAILED")
            print("❌ Address performance issues before staging")

    finally:
        consumer = get_analytics_consumer()
        await consumer.stop()
        consumer_task.cancel()

if __name__ == "__main__":
    asyncio.run(run_load_test())