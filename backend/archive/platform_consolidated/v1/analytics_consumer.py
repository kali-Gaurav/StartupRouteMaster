"""
Minimal Analytics Consumer for Railway Events

Phase 4 - Step 1: Single consumer for all 3 event types
"""

import asyncio
import json
import logging
from typing import Dict, Any
from datetime import datetime
from config import Config
from utils.metrics import CONSUMER_LAG_SECONDS
from services.delay_predictor import delay_predictor

logger = logging.getLogger(__name__)

class AnalyticsConsumer:
    """Simple analytics consumer that processes events"""

    def __init__(self):
        self.event_counts: Dict[str, int] = {}
        self.processing_stats: Dict[str, Any] = {}
        self.is_running = False
        self.last_message_time = None
        self.processed_events = 0
        self.consumer_lag_estimate = 0  # Rough estimate in seconds

    async def start_consuming(self):
        """Start consuming events from all topics"""
        if not Config.KAFKA_ENABLE_EVENTS:
            logger.info("Kafka events disabled, analytics consumer not starting")
            return

        try:
            from aiokafka import AIOKafkaConsumer

            consumer = AIOKafkaConsumer(
                'route_events', 'booking_events', 'delay_events',
                bootstrap_servers=Config.KAFKA_BOOTSTRAP_SERVERS,
                group_id='analytics_consumer',
                auto_offset_reset='latest',
                value_deserializer=lambda v: json.loads(v.decode('utf-8')),
                # Minimal backbone configuration: controlled commits
                enable_auto_commit=True,  # Auto-commit for simplicity
                auto_commit_interval_ms=5000,  # Commit every 5 seconds
                max_poll_records=100,  # Process in small batches
                session_timeout_ms=30000,  # 30s session timeout
                heartbeat_interval_ms=3000,  # 3s heartbeats
            )

            await consumer.start()
            self.is_running = True
            logger.info("Analytics consumer started")

            async for message in consumer:
                try:
                    await self.process_event(message.value, message.topic)
                except Exception as e:
                    logger.error(f"Error processing event from {message.topic}: {e}")

        except ImportError:
            logger.warning("aiokafka not available, analytics consumer cannot start")
        except Exception as e:
            logger.error(f"Failed to start analytics consumer: {e}")
        finally:
            self.is_running = False

    async def process_event(self, event_data: Dict[str, Any], topic: str):
        """Process individual event"""
        self.last_message_time = datetime.utcnow()
        self.processed_events += 1

        event_type = event_data.get('event_type', 'unknown')

        # Update counters
        if event_type not in self.event_counts:
            self.event_counts[event_type] = 0
        self.event_counts[event_type] += 1

        # Process based on event type
        if event_type == 'RouteSearched':
            await self._process_route_searched(event_data)
        elif event_type == 'BookingCreated':
            await self._process_booking_created(event_data)
        elif event_type == 'TrainDelayed':
            await self._process_train_delayed(event_data)
        else:
            logger.warning(f"Unknown event type: {event_type}")

        # Log stats every 100 events
        total_events = sum(self.event_counts.values())
        if total_events % 100 == 0:
            logger.info(f"Processed {total_events} events: {self.event_counts}")

    async def _process_route_searched(self, event: Dict[str, Any]):
        """Process route search analytics"""
        # Simple analytics: count searches by route popularity
        source = event.get('source', 'unknown')
        destination = event.get('destination', 'unknown')
        routes_shown = event.get('routes_shown', 0)
        latency = event.get('search_latency_ms', 0)

        # Update route popularity stats
        route_key = f"{source}-{destination}"
        if route_key not in self.processing_stats:
            self.processing_stats[route_key] = {
                'searches': 0,
                'total_routes_shown': 0,
                'total_latency': 0
            }

        stats = self.processing_stats[route_key]
        stats['searches'] += 1
        stats['total_routes_shown'] += routes_shown
        stats['total_latency'] += latency

        logger.debug(f"Route search: {route_key}, latency: {latency:.2f}ms")

    async def _process_booking_created(self, event: Dict[str, Any]):
        """Process booking analytics"""
        user_id = event.get('user_id', 'anonymous')
        total_cost = event.get('total_cost', 0)
        segments = event.get('segments', [])

        # Simple booking stats
        if 'bookings' not in self.processing_stats:
            self.processing_stats['bookings'] = {
                'total': 0,
                'total_revenue': 0,
                'avg_segments': 0
            }

        bookings = self.processing_stats['bookings']
        bookings['total'] += 1
        bookings['total_revenue'] += total_cost
        bookings['avg_segments'] = ((bookings['avg_segments'] * (bookings['total'] - 1)) + len(segments)) / bookings['total']

        logger.debug(f"Booking created: {user_id}, cost: ₹{total_cost}, segments: {len(segments)}")

    async def _process_train_delayed(self, event: Dict[str, Any]):
        """Process delay analytics"""
        train_id = event.get('train_id', 'unknown')
        delay_minutes = event.get('delay_minutes', 0)
        station_code = event.get('station_code', 'unknown')
        scheduled_departure = event.get('scheduled_departure', '')
        estimated_departure = event.get('estimated_departure', '')
        reason = event.get('reason')

        # Update real-time delay map for route engine intelligence
        if isinstance(train_id, int):  # Ensure train_id is valid
            await delay_predictor.update_real_time_delay(
                train_id=train_id,
                delay_minutes=delay_minutes,
                station_code=station_code,
                scheduled_departure=scheduled_departure,
                estimated_departure=estimated_departure,
                reason=reason
            )

        # Simple delay stats
        if 'delays' not in self.processing_stats:
            self.processing_stats['delays'] = {
                'total': 0,
                'avg_delay': 0,
                'max_delay': 0
            }

        delays = self.processing_stats['delays']
        delays['total'] += 1
        delays['avg_delay'] = ((delays['avg_delay'] * (delays['total'] - 1)) + delay_minutes) / delays['total']
        delays['max_delay'] = max(delays['max_delay'], delay_minutes)

        logger.debug(f"Train delay: {train_id} at {station_code}, {delay_minutes} minutes")

    def get_stats(self) -> Dict[str, Any]:
        """Get current processing statistics"""
        # Estimate lag as time since last message (rough approximation)
        if self.last_message_time:
            self.consumer_lag_estimate = (datetime.utcnow() - self.last_message_time).total_seconds()
        else:
            self.consumer_lag_estimate = 0

        # Record consumer lag metrics
        if CONSUMER_LAG_SECONDS is not None:
            # Record for each topic (simplified - using 'all' as topic)
            CONSUMER_LAG_SECONDS.labels(topic='all', partition='0').set(self.consumer_lag_estimate)

        return {
            'event_counts': self.event_counts.copy(),
            'processing_stats': self.processing_stats.copy(),
            'is_running': self.is_running,
            'processed_events': self.processed_events,
            'consumer_lag_estimate_seconds': self.consumer_lag_estimate,
            'last_message_time': self.last_message_time.isoformat() if self.last_message_time else None,
            'timestamp': datetime.utcnow().isoformat()
        }

    async def stop(self):
        """Stop the consumer"""
        self.is_running = False
        logger.info("Analytics consumer stopped")

# Global consumer instance
_analytics_consumer = None

def get_analytics_consumer() -> AnalyticsConsumer:
    """Get or create analytics consumer instance"""
    global _analytics_consumer
    if _analytics_consumer is None:
        _analytics_consumer = AnalyticsConsumer()
    return _analytics_consumer

async def start_analytics_consumer():
    """Start the analytics consumer as a background task"""
    consumer = get_analytics_consumer()
    await consumer.start_consuming()

# For running as standalone service
async def main():
    """Run analytics consumer as standalone service"""
    logging.basicConfig(level=logging.INFO)
    logger.info("Starting Railway Analytics Consumer")

    consumer = get_analytics_consumer()

    # Handle graceful shutdown
    def signal_handler():
        logger.info("Received shutdown signal")
        consumer.stop()

    try:
        await consumer.start_consuming()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        await consumer.stop()

if __name__ == "__main__":
    asyncio.run(main())
