"""
Cache Warming Service - Precompute and Cache Popular Data

Precomputes and caches frequently accessed data to achieve IRCTC-level performance:
- Popular route queries
- Station reachability graphs
- High-demand availability data
- ML features for common routes

Key Features:
- Scheduled cache warming
- Popularity-based prioritization
- Memory-efficient precomputation
- Automatic cache refresh
"""

import asyncio
import logging
from datetime import datetime, date, timedelta
from typing import List, Dict, Set, Any
from collections import defaultdict

from sqlalchemy import func, and_, desc
from sqlalchemy.orm import Session

from ..database import SessionLocal
from ..models import Trip, StopTime, Station
from ..route_engine import RouteEngine, RouteConstraints
from ..availability_service import availability_service, AvailabilityRequest
from ..services.multi_layer_cache import multi_layer_cache, RouteQuery, AvailabilityQuery
from ..seat_inventory_models import QuotaType
from ..config import Config

logger = logging.getLogger(__name__)


class CacheWarmingService:
    """
    Service for warming caches with popular and frequently accessed data
    """

    def __init__(self):
        self.route_engine = RouteEngine()
        self._is_warming = False

    async def start_warming_cycle(self):
        """Start the cache warming cycle"""
        if self._is_warming:
            logger.info("Cache warming already in progress")
            return

        self._is_warming = True
        try:
            logger.info("Starting cache warming cycle")

            # Warm caches in parallel
            await asyncio.gather(
                self._warm_popular_routes(),
                self._warm_station_reachability(),
                self._warm_popular_availability(),
                self._warm_ml_features()
            )

            logger.info("Cache warming cycle completed")

        except Exception as e:
            logger.error(f"Cache warming failed: {e}")
        finally:
            self._is_warming = False

    async def _warm_popular_routes(self):
        """Warm route cache with popular station pairs"""
        logger.info("Warming popular routes cache")

        # Get popular station pairs (simplified - in production, use actual search logs)
        popular_pairs = await self._get_popular_station_pairs()

        constraints = RouteConstraints(
            max_transfers=3,
            max_results=5,
            include_wait_time=True
        )

        # Warm routes for next 7 days
        for days_ahead in range(7):
            travel_date = date.today() + timedelta(days=days_ahead + 1)  # Tomorrow onwards

            for from_station, to_station in popular_pairs[:20]:  # Limit to top 20
                try:
                    # Create cache query
                    cache_query = RouteQuery(
                        from_station=str(from_station),
                        to_station=str(to_station),
                        date=travel_date,
                        max_transfers=3,
                        include_wait_time=True
                    )

                    # Check if already cached
                    cached = await multi_layer_cache.get_route_query(cache_query)
                    if cached:
                        continue

                    # Compute routes
                    departure_datetime = datetime.combine(travel_date, datetime.min.time())
                    routes = await self.route_engine._compute_routes(
                        from_station, to_station, departure_datetime, constraints
                    )

                    if routes:
                        # Cache the result
                        serialized = self.route_engine._serialize_routes_for_cache(routes)
                        await multi_layer_cache.set_route_query(cache_query, serialized)

                        logger.debug(f"Warmed route cache: {from_station} -> {to_station} on {travel_date}")

                except Exception as e:
                    logger.error(f"Failed to warm route {from_station}->{to_station}: {e}")

    async def _warm_station_reachability(self):
        """Precompute station reachability graphs"""
        logger.info("Warming station reachability cache")

        session = SessionLocal()
        try:
            # Get major stations (simplified - in production, use station importance metrics)
            major_stations = session.query(Station).limit(100).all()

            for station in major_stations:
                for max_transfers in [1, 2, 3]:
                    # Check if already cached
                    cached = await multi_layer_cache.get_station_reachability(station.id, max_transfers)
                    if cached is not None:
                        continue

                    # Compute reachability
                    reachable = await multi_layer_cache._compute_reachable_stations(
                        session, station.id, max_transfers
                    )

                    if reachable:
                        await multi_layer_cache.set_station_reachability(station.id, reachable, max_transfers)
                        logger.debug(f"Warmed reachability for station {station.id} ({max_transfers} transfers)")

        finally:
            session.close()

    async def _warm_popular_availability(self):
        """Warm availability cache for popular routes and dates"""
        logger.info("Warming popular availability cache")

        # Get popular train routes (simplified)
        popular_routes = await self._get_popular_train_routes()

        # Check next 3 days
        for days_ahead in range(3):
            travel_date = date.today() + timedelta(days=days_ahead + 1)

            for route_info in popular_routes[:50]:  # Top 50 routes
                try:
                    trip_id = route_info['trip_id']
                    from_stop = route_info['from_stop_id']
                    to_stop = route_info['to_stop_id']

                    # Check all quota types
                    for quota in QuotaType:
                        cache_query = AvailabilityQuery(
                            train_id=trip_id,
                            from_stop_id=from_stop,
                            to_stop_id=to_stop,
                            travel_date=travel_date,
                            quota_type=quota.value,
                            passengers=1
                        )

                        # Check if already cached
                        cached = await multi_layer_cache.get_availability(cache_query)
                        if cached:
                            continue

                        # Compute availability
                        avail_request = AvailabilityRequest(
                            trip_id=trip_id,
                            from_stop_id=from_stop,
                            to_stop_id=to_stop,
                            travel_date=travel_date,
                            quota_type=quota,
                            passengers=1
                        )

                        response = await availability_service._check_availability_db(avail_request)

                        # Cache the result
                        await multi_layer_cache.set_availability(cache_query, response.__dict__)

                        logger.debug(f"Warmed availability: train {trip_id}, {from_stop}->{to_stop}, {quota.value}")

                except Exception as e:
                    logger.error(f"Failed to warm availability for route {route_info}: {e}")

    async def _warm_ml_features(self):
        """Warm ML feature cache for popular routes"""
        logger.info("Warming ML features cache")

        # This would integrate with your ML service
        # For now, just log that it would happen
        logger.info("ML feature warming would happen here (integrate with ML service)")

    async def _get_popular_station_pairs(self) -> List[tuple]:
        """Get popular station pairs (simplified implementation)"""
        session = SessionLocal()
        try:
            # In production, this would analyze search logs, booking data, etc.
            # For now, return some major Indian railway station pairs
            major_stations = [
                (1, 2),   # Delhi -> Mumbai
                (1, 3),   # Delhi -> Kolkata
                (1, 4),   # Delhi -> Chennai
                (2, 1),   # Mumbai -> Delhi
                (2, 3),   # Mumbai -> Kolkata
                (3, 1),   # Kolkata -> Delhi
                (3, 2),   # Kolkata -> Mumbai
                (4, 1),   # Chennai -> Delhi
            ]
            return major_stations

        finally:
            session.close()

    async def _get_popular_train_routes(self) -> List[Dict]:
        """Get popular train routes (simplified implementation)"""
        session = SessionLocal()
        try:
            # Get some active trips with their stop sequences
            trips = session.query(Trip).filter(Trip.status == "ACTIVE").limit(20).all()

            routes = []
            for trip in trips:
                # Get stop sequence for this trip
                stops = session.query(StopTime).filter(
                    StopTime.trip_id == trip.id
                ).order_by(StopTime.stop_sequence).all()

                if len(stops) >= 2:
                    # Add route from first to last stop
                    routes.append({
                        'trip_id': trip.id,
                        'from_stop_id': stops[0].stop_id,
                        'to_stop_id': stops[-1].stop_id
                    })

            return routes

        finally:
            session.close()

    async def get_warming_status(self) -> Dict:
        """Get cache warming status and statistics"""
        cache_stats = await multi_layer_cache.get_cache_stats()

        return {
            'is_warming': self._is_warming,
            'cache_stats': cache_stats,
            'last_warming_cycle': datetime.utcnow().isoformat()  # In production, track this
        }


# Global instance
cache_warming_service = CacheWarmingService()


# ============================================================================
# SCHEDULER INTEGRATION
# ============================================================================

async def schedule_cache_warming():
    """Schedule periodic cache warming"""
    while True:
        try:
            # Run warming cycle every 30 minutes during peak hours
            # In production, this would be more sophisticated
            await cache_warming_service.start_warming_cycle()

            # Wait 30 minutes
            await asyncio.sleep(30 * 60)

        except Exception as e:
            logger.error(f"Scheduled cache warming failed: {e}")
            await asyncio.sleep(5 * 60)  # Wait 5 minutes on error


# ============================================================================
# MANUAL CACHE MANAGEMENT
# ============================================================================

async def manual_cache_warmup():
    """Manually trigger cache warming (for admin operations)"""
    logger.info("Manual cache warmup initiated")
    await cache_warming_service.start_warming_cycle()
    logger.info("Manual cache warmup completed")


async def clear_all_caches():
    """Clear all caches (for maintenance/debugging)"""
    logger.warning("Clearing all caches")

    # This would need to be implemented in multi_layer_cache
    # For now, just log
    logger.info("All caches cleared (not implemented yet)")


async def get_cache_health_report() -> Dict:
    """Get comprehensive cache health report"""
    warming_status = await cache_warming_service.get_warming_status()
    cache_stats = await multi_layer_cache.get_cache_stats()
    health = await multi_layer_cache.health_check()

    return {
        'cache_healthy': health,
        'warming_status': warming_status,
        'cache_stats': cache_stats,
        'recommendations': _generate_cache_recommendations(cache_stats)
    }


def _generate_cache_recommendations(cache_stats: Dict) -> List[str]:
    """Generate cache optimization recommendations"""
    recommendations = []

    # Check hit rates
    for layer, stats in cache_stats.items():
        if isinstance(stats, dict) and 'hit_rate' in stats:
            hit_rate = stats['hit_rate']
            if hit_rate < 0.5:
                recommendations.append(f"Low hit rate ({hit_rate:.2%}) for {layer} - consider increasing TTL or cache size")
            elif hit_rate > 0.9:
                recommendations.append(f"Excellent hit rate ({hit_rate:.2%}) for {layer}")

    # Check if Redis is connected
    if 'redis' not in cache_stats or not cache_stats.get('redis', {}).get('connected_clients', 0) > 0:
        recommendations.append("Redis not connected - falling back to in-memory cache")

    return recommendations if recommendations else ["Cache performance looks good"]
