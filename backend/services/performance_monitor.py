"""
Performance Monitoring Service - IRCTC-Level System Metrics

Monitors and reports on system performance to maintain IRCTC-level speed:
- Cache hit rates and latency
- Query performance metrics
- System resource usage
- Performance degradation alerts
- Auto-scaling triggers

Key Features:
- Real-time performance tracking
- Performance regression detection
- Automated alerting
- Performance dashboards
- Historical trend analysis
"""

import asyncio
import time
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional
from collections import defaultdict, deque
import statistics

from ..services.multi_layer_cache import multi_layer_cache
from ..config import Config

logger = logging.getLogger(__name__)


class PerformanceMetrics:
    """Container for performance metrics"""

    def __init__(self):
        self.reset()

    def reset(self):
        """Reset all metrics"""
        self.route_query_count = 0
        self.route_query_latencies = deque(maxlen=1000)
        self.availability_query_count = 0
        self.availability_query_latencies = deque(maxlen=1000)
        self.booking_operation_count = 0
        self.booking_operation_latencies = deque(maxlen=1000)

        self.cache_hits = defaultdict(int)
        self.cache_misses = defaultdict(int)
        self.cache_sets = defaultdict(int)
        self.cache_deletes = defaultdict(int)

        self.error_count = 0
        self.last_reset = datetime.utcnow()

    def record_route_query(self, latency_ms: float):
        """Record route query performance"""
        self.route_query_count += 1
        self.route_query_latencies.append(latency_ms)

    def record_availability_query(self, latency_ms: float):
        """Record availability query performance"""
        self.availability_query_count += 1
        self.availability_query_latencies.append(latency_ms)

    def record_booking_operation(self, latency_ms: float):
        """Record booking operation performance"""
        self.booking_operation_count += 1
        self.booking_operation_latencies.append(latency_ms)

    def record_cache_operation(self, layer: str, operation: str):
        """Record cache operation"""
        if operation == 'hit':
            self.cache_hits[layer] += 1
        elif operation == 'miss':
            self.cache_misses[layer] += 1
        elif operation == 'set':
            self.cache_sets[layer] += 1
        elif operation == 'delete':
            self.cache_deletes[layer] += 1

    def record_error(self):
        """Record error occurrence"""
        self.error_count += 1

    def get_summary(self) -> Dict[str, Any]:
        """Get performance summary"""
        def safe_stats(latencies):
            if not latencies:
                return {'avg': 0, 'p95': 0, 'p99': 0, 'min': 0, 'max': 0}
            sorted_latencies = sorted(latencies)
            return {
                'avg': statistics.mean(sorted_latencies),
                'p95': sorted_latencies[int(len(sorted_latencies) * 0.95)],
                'p99': sorted_latencies[int(len(sorted_latencies) * 0.99)],
                'min': min(sorted_latencies),
                'max': max(sorted_latencies)
            }

        return {
            'time_range': {
                'from': self.last_reset.isoformat(),
                'to': datetime.utcnow().isoformat()
            },
            'route_queries': {
                'count': self.route_query_count,
                'latency_ms': safe_stats(self.route_query_latencies)
            },
            'availability_queries': {
                'count': self.availability_query_count,
                'latency_ms': safe_stats(self.availability_query_latencies)
            },
            'booking_operations': {
                'count': self.booking_operation_count,
                'latency_ms': safe_stats(self.booking_operation_latencies)
            },
            'cache_performance': {
                layer: {
                    'hits': self.cache_hits[layer],
                    'misses': self.cache_misses[layer],
                    'sets': self.cache_sets[layer],
                    'deletes': self.cache_deletes[layer],
                    'hit_rate': (self.cache_hits[layer] / max(1, self.cache_hits[layer] + self.cache_misses[layer]))
                } for layer in set(list(self.cache_hits.keys()) + list(self.cache_misses.keys()))
            },
            'errors': {
                'count': self.error_count,
                'error_rate': self.error_count / max(1, self.route_query_count + self.availability_query_count + self.booking_operation_count)
            }
        }


class PerformanceMonitor:
    """
    Monitors system performance and provides insights for optimization
    """

    def __init__(self):
        self.metrics = PerformanceMetrics()
        self.alerts = []
        self.performance_history = deque(maxlen=100)  # Keep last 100 measurements
        self._monitoring = False

    async def start_monitoring(self):
        """Start performance monitoring"""
        if self._monitoring:
            return

        self._monitoring = True
        logger.info("Starting performance monitoring")

        # Start monitoring loop
        asyncio.create_task(self._monitoring_loop())

    async def stop_monitoring(self):
        """Stop performance monitoring"""
        self._monitoring = False
        logger.info("Stopped performance monitoring")

    async def _monitoring_loop(self):
        """Main monitoring loop"""
        while self._monitoring:
            try:
                # Collect metrics every 60 seconds
                await asyncio.sleep(60)

                # Get current performance snapshot
                snapshot = await self._collect_performance_snapshot()

                # Store in history
                self.performance_history.append(snapshot)

                # Check for performance issues
                alerts = self._analyze_performance(snapshot)
                if alerts:
                    self.alerts.extend(alerts)
                    for alert in alerts:
                        logger.warning(f"Performance Alert: {alert}")

                # Reset metrics for next period
                self.metrics.reset()

            except Exception as e:
                logger.error(f"Performance monitoring error: {e}")

    async def _collect_performance_snapshot(self) -> Dict[str, Any]:
        """Collect current performance snapshot"""
        cache_stats = await multi_layer_cache.get_cache_stats()

        return {
            'timestamp': datetime.utcnow().isoformat(),
            'metrics': self.metrics.get_summary(),
            'cache_stats': cache_stats,
            'system_health': await self._check_system_health()
        }

    async def _check_system_health(self) -> Dict[str, Any]:
        """Check overall system health"""
        health = {
            'cache_healthy': await multi_layer_cache.health_check(),
            'database_connections': 'unknown',  # Would integrate with DB monitoring
            'memory_usage': 'unknown',  # Would integrate with system monitoring
            'cpu_usage': 'unknown'  # Would integrate with system monitoring
        }

        return health

    def _analyze_performance(self, snapshot: Dict) -> List[str]:
        """Analyze performance and generate alerts"""
        alerts = []

        metrics = snapshot['metrics']

        # Check route query performance
        route_latency = metrics['route_queries']['latency_ms']
        if route_latency['p95'] > 100:  # 100ms P95 target
            alerts.append(".1f")

        if route_latency['p99'] > 500:  # 500ms P99 target
            alerts.append(".1f")

        # Check availability query performance
        avail_latency = metrics['availability_queries']['latency_ms']
        if avail_latency['p95'] > 50:  # 50ms P95 target
            alerts.append(".1f")

        # Check cache hit rates
        cache_perf = metrics['cache_performance']
        for layer, stats in cache_perf.items():
            if stats['hit_rate'] < 0.6:  # 60% minimum hit rate
                alerts.append(".2%")

        # Check error rates
        error_rate = metrics['errors']['error_rate']
        if error_rate > 0.05:  # 5% maximum error rate
            alerts.append(".2%")

        return alerts

    def record_route_query_latency(self, latency_ms: float):
        """Record route query latency"""
        self.metrics.record_route_query_latency(latency_ms)

    def record_availability_query_latency(self, latency_ms: float):
        """Record availability query latency"""
        self.metrics.record_availability_query_latency(latency_ms)

    def record_booking_operation_latency(self, latency_ms: float):
        """Record booking operation latency"""
        self.metrics.record_booking_operation_latency(latency_ms)

    def record_cache_operation(self, layer: str, operation: str):
        """Record cache operation"""
        self.metrics.record_cache_operation(layer, operation)

    def record_error(self):
        """Record error"""
        self.metrics.record_error()

    async def get_performance_report(self) -> Dict[str, Any]:
        """Get comprehensive performance report"""
        current_snapshot = await self._collect_performance_snapshot()

        # Calculate trends
        trends = self._calculate_trends()

        return {
            'current': current_snapshot,
            'trends': trends,
            'alerts': self.alerts[-10:],  # Last 10 alerts
            'recommendations': self._generate_recommendations(current_snapshot)
        }

    def _calculate_trends(self) -> Dict[str, Any]:
        """Calculate performance trends"""
        if len(self.performance_history) < 2:
            return {'insufficient_data': True}

        # Calculate trends over last few snapshots
        recent = list(self.performance_history)[-5:]  # Last 5 snapshots

        trends = {
            'route_query_p95_trend': self._calculate_metric_trend(
                recent, lambda s: s['metrics']['route_queries']['latency_ms']['p95']
            ),
            'availability_query_p95_trend': self._calculate_metric_trend(
                recent, lambda s: s['metrics']['availability_queries']['latency_ms']['p95']
            ),
            'cache_hit_rate_trend': self._calculate_metric_trend(
                recent, lambda s: s['metrics']['cache_performance'].get('query_cache', {}).get('hit_rate', 0)
            )
        }

        return trends

    def _calculate_metric_trend(self, snapshots: List[Dict], metric_func) -> str:
        """Calculate trend for a metric"""
        values = [metric_func(s) for s in snapshots if metric_func(s) is not None]

        if len(values) < 2:
            return 'insufficient_data'

        # Simple linear trend
        if values[-1] > values[0] * 1.1:  # 10% increase
            return 'increasing'
        elif values[-1] < values[0] * 0.9:  # 10% decrease
            return 'decreasing'
        else:
            return 'stable'

    def _generate_recommendations(self, snapshot: Dict) -> List[str]:
        """Generate performance optimization recommendations"""
        recommendations = []

        metrics = snapshot['metrics']

        # Route query recommendations
        route_p95 = metrics['route_queries']['latency_ms']['p95']
        if route_p95 > 100:
            recommendations.append("Route query P95 latency too high. Consider increasing route cache TTL or precomputing more routes.")

        # Cache recommendations
        cache_perf = metrics['cache_performance']
        for layer, stats in cache_perf.items():
            hit_rate = stats['hit_rate']
            if hit_rate < 0.7:
                recommendations.append(f"Low cache hit rate for {layer} ({hit_rate:.1%}). Consider warming more data or increasing cache size.")

        # Error rate recommendations
        error_rate = metrics['errors']['error_rate']
        if error_rate > 0.01:
            recommendations.append(f"High error rate ({error_rate:.2%}). Investigate and fix root causes.")

        return recommendations if recommendations else ["Performance looks good. Keep monitoring."]

    async def export_metrics_for_monitoring(self) -> Dict[str, Any]:
        """Export metrics in format suitable for external monitoring systems"""
        snapshot = await self._collect_performance_snapshot()

        # Convert to Prometheus-style metrics
        metrics = snapshot['metrics']

        return {
            'railway_route_query_total': metrics['route_queries']['count'],
            'railway_route_query_latency_p95': metrics['route_queries']['latency_ms']['p95'],
            'railway_availability_query_total': metrics['availability_queries']['count'],
            'railway_availability_query_latency_p95': metrics['availability_queries']['latency_ms']['p95'],
            'railway_booking_operation_total': metrics['booking_operations']['count'],
            'railway_booking_operation_latency_p95': metrics['booking_operations']['latency_ms']['p95'],
            'railway_cache_hit_rate': {
                layer: stats['hit_rate']
                for layer, stats in metrics['cache_performance'].items()
            },
            'railway_error_rate': metrics['errors']['error_rate']
        }


# Global instance
performance_monitor = PerformanceMonitor()


# ============================================================================
# DECORATORS FOR AUTOMATIC MONITORING
# ============================================================================

def monitor_route_query(func):
    """Decorator to monitor route query performance"""
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            latency_ms = (time.time() - start_time) * 1000
            performance_monitor.record_route_query_latency(latency_ms)
            return result
        except Exception as e:
            performance_monitor.record_error()
            raise
    return wrapper


def monitor_availability_query(func):
    """Decorator to monitor availability query performance"""
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            latency_ms = (time.time() - start_time) * 1000
            performance_monitor.record_availability_query_latency(latency_ms)
            return result
        except Exception as e:
            performance_monitor.record_error()
            raise
    return wrapper


def monitor_booking_operation(func):
    """Decorator to monitor booking operation performance"""
    async def wrapper(*args, **kwargs):
        start_time = time.time()
        try:
            result = await func(*args, **kwargs)
            latency_ms = (time.time() - start_time) * 1000
            performance_monitor.record_booking_operation_latency(latency_ms)
            return result
        except Exception as e:
            performance_monitor.record_error()
            raise
    return wrapper


def monitor_cache_operation(layer: str):
    """Decorator to monitor cache operations"""
    def decorator(func):
        async def wrapper(*args, **kwargs):
            try:
                result = await func(*args, **kwargs)
                # Determine operation type from function name
                if 'get' in func.__name__:
                    if result is not None:
                        performance_monitor.record_cache_operation(layer, 'hit')
                    else:
                        performance_monitor.record_cache_operation(layer, 'miss')
                elif 'set' in func.__name__:
                    performance_monitor.record_cache_operation(layer, 'set')
                elif 'delete' in func.__name__ or 'invalidate' in func.__name__:
                    performance_monitor.record_cache_operation(layer, 'delete')
                return result
            except Exception as e:
                performance_monitor.record_error()
                raise
        return wrapper
    return decorator


# ============================================================================
# PERFORMANCE DASHBOARD
# ============================================================================

async def get_performance_dashboard() -> Dict[str, Any]:
    """Get performance dashboard data"""
    report = await performance_monitor.get_performance_report()

    # Format for dashboard display
    dashboard = {
        'summary': {
            'route_queries_per_minute': report['current']['metrics']['route_queries']['count'],
            'avg_route_latency_ms': report['current']['metrics']['route_queries']['latency_ms']['avg'],
            'cache_hit_rate': report['current']['metrics']['cache_performance'].get('query_cache', {}).get('hit_rate', 0),
            'error_rate': report['current']['metrics']['errors']['error_rate']
        },
        'charts': {
            'route_latency_trend': [],  # Would populate with historical data
            'cache_hit_rate_trend': [],
            'error_rate_trend': []
        },
        'alerts': report['alerts'],
        'recommendations': report['recommendations']
    }

    return dashboard


# ============================================================================
# HEALTH CHECK ENDPOINT
# ============================================================================

async def system_health_check() -> Dict[str, Any]:
    """Comprehensive system health check"""
    cache_health = await multi_layer_cache.health_check()
    performance_report = await performance_monitor.get_performance_report()

    # Determine overall health
    overall_healthy = True
    issues = []

    if not cache_health:
        overall_healthy = False
        issues.append("Cache system unhealthy")

    metrics = performance_report['current']['metrics']
    if metrics['route_queries']['latency_ms']['p95'] > 200:
        overall_healthy = False
        issues.append("Route query latency too high")

    if metrics['errors']['error_rate'] > 0.1:
        overall_healthy = False
        issues.append("High error rate")

    return {
        'healthy': overall_healthy,
        'issues': issues,
        'cache_healthy': cache_health,
        'performance_metrics': metrics,
        'timestamp': datetime.utcnow().isoformat()
    }
