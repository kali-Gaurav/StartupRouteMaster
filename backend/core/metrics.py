"""
Shared Metrics Framework - Unified Performance Tracking

Consolidates metrics tracking across:
- cache/manager.py (CacheMetrics)
- inventory/seat_allocator.py (occupancy statistics)
- routing/engine.py (performance monitoring)
- pricing/engine.py (pricing decision tracking)

Features:
- Per-layer metrics tracking
- Hit rate calculation
- Performance percentile tracking
- Automated reporting
"""

import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict, field
from datetime import datetime, timedelta
from collections import deque
import statistics

logger = logging.getLogger(__name__)


@dataclass
class PerformanceMetric:
    """Single performance metric point."""
    name: str
    value: float
    unit: str = "ms"
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict:
        """Convert to dictionary."""
        return {
            'name': self.name,
            'value': self.value,
            'unit': self.unit,
            'timestamp': self.timestamp.isoformat(),
            'metadata': self.metadata,
        }


class MetricsCollector:
    """
    Collects and tracks metrics for any system component.

    Supports:
    - Counter metrics (hits, misses, operations)
    - Gauge metrics (occupancy, queue size)
    - Histogram metrics (latencies, sizes)
    - Summary metrics (average, percentiles)
    """

    def __init__(self, name: str, window_size: int = 1000):
        """
        Initialize metrics collector.

        Args:
            name: Component name (e.g., 'route_cache', 'seat_allocator')
            window_size: Max metrics to keep in rolling window
        """
        self.name = name
        self.window_size = window_size

        # Counter metrics (always increasing)
        self.counters: Dict[str, int] = {}

        # Gauge metrics (current value)
        self.gauges: Dict[str, float] = {}

        # Histogram metrics (rolling window of values)
        self.histograms: Dict[str, deque] = {}

        # Metadata
        self.created_at = datetime.utcnow()
        self.last_reset = datetime.utcnow()

    # =========================================================================
    # COUNTER OPERATIONS
    # =========================================================================

    def increment_counter(self, name: str, value: int = 1):
        """Increment a counter metric."""
        if name not in self.counters:
            self.counters[name] = 0
        self.counters[name] += value

    def get_counter(self, name: str) -> int:
        """Get counter value."""
        return self.counters.get(name, 0)

    def reset_counter(self, name: str):
        """Reset a counter to zero."""
        self.counters[name] = 0

    # =========================================================================
    # GAUGE OPERATIONS
    # =========================================================================

    def set_gauge(self, name: str, value: float):
        """Set a gauge metric to a value."""
        self.gauges[name] = value

    def get_gauge(self, name: str) -> float:
        """Get gauge value."""
        return self.gauges.get(name, 0.0)

    def increment_gauge(self, name: str, value: float = 1.0):
        """Increment gauge value."""
        if name not in self.gauges:
            self.gauges[name] = 0.0
        self.gauges[name] += value

    def decrement_gauge(self, name: str, value: float = 1.0):
        """Decrement gauge value."""
        self.increment_gauge(name, -value)

    # =========================================================================
    # HISTOGRAM OPERATIONS
    # =========================================================================

    def record_histogram(self, name: str, value: float):
        """Record a value in histogram."""
        if name not in self.histograms:
            self.histograms[name] = deque(maxlen=self.window_size)
        self.histograms[name].append(value)

    def get_histogram_stats(self, name: str) -> Dict[str, float]:
        """Get statistics for a histogram."""
        if name not in self.histograms or len(self.histograms[name]) == 0:
            return {
                'count': 0,
                'min': 0.0,
                'max': 0.0,
                'mean': 0.0,
                'median': 0.0,
                'p95': 0.0,
                'p99': 0.0,
            }

        values = list(self.histograms[name])
        values.sort()

        return {
            'count': len(values),
            'min': float(min(values)),
            'max': float(max(values)),
            'mean': float(statistics.mean(values)),
            'median': float(statistics.median(values)),
            'p95': float(values[int(len(values) * 0.95)] if len(values) > 0 else 0),
            'p99': float(values[int(len(values) * 0.99)] if len(values) > 0 else 0),
        }

    # =========================================================================
    # COMPOSITE METRICS
    # =========================================================================

    def calculate_hit_rate(self, hits_counter: str, misses_counter: str) -> float:
        """Calculate cache hit rate from two counters."""
        hits = self.get_counter(hits_counter)
        misses = self.get_counter(misses_counter)
        total = hits + misses
        return hits / total if total > 0 else 0.0

    def calculate_occupancy_rate(self, used_gauge: str, total_gauge: str) -> float:
        """Calculate occupancy rate from two gauges."""
        used = self.get_gauge(used_gauge)
        total = self.get_gauge(total_gauge)
        return used / total if total > 0 else 0.0

    def get_uptime_seconds(self) -> float:
        """Get seconds since metrics collector created."""
        return (datetime.utcnow() - self.created_at).total_seconds()

    # =========================================================================
    # REPORTING
    # =========================================================================

    def get_summary(self) -> Dict[str, Any]:
        """Get complete metrics summary."""
        histogram_stats = {}
        for name in self.histograms:
            histogram_stats[name] = self.get_histogram_stats(name)

        return {
            'name': self.name,
            'uptime_seconds': self.get_uptime_seconds(),
            'counters': self.counters,
            'gauges': self.gauges,
            'histograms': histogram_stats,
            'created_at': self.created_at.isoformat(),
            'last_reset': self.last_reset.isoformat(),
        }

    def reset_all(self):
        """Reset all metrics."""
        self.counters.clear()
        self.gauges.clear()
        self.histograms.clear()
        self.last_reset = datetime.utcnow()
        logger.info(f"Reset all metrics for {self.name}")

    # =========================================================================
    # LOGGING & EXPORT
    # =========================================================================

    def log_summary(self):
        """Log metrics summary."""
        summary = self.get_summary()
        logger.info(f"Metrics summary for {self.name}:")
        logger.info(f"  Uptime: {summary['uptime_seconds']:.1f}s")
        logger.info(f"  Counters: {summary['counters']}")
        logger.info(f"  Gauges: {summary['gauges']}")

    def export_prometheus(self) -> str:
        """Export metrics in Prometheus format."""
        lines = []

        # Counters
        for name, value in self.counters.items():
            lines.append(f"{self.name}_{name}_total {value}")

        # Gauges
        for name, value in self.gauges.items():
            lines.append(f"{self.name}_{name} {value}")

        # Histograms (count, sum, buckets)
        for name, values in self.histograms.items():
            if len(values) > 0:
                total = sum(values)
                lines.append(f"{self.name}_{name}_sum {total}")
                lines.append(f"{self.name}_{name}_count {len(values)}")

        return "\n".join(lines)


# ==============================================================================
# SPECIALIZED COLLECTORS FOR SPECIFIC USE CASES
# ==============================================================================

class CacheMetricsCollector(MetricsCollector):
    """Specialized metrics for cache operations."""

    def record_cache_hit(self):
        """Record a cache hit."""
        self.increment_counter('hits')

    def record_cache_miss(self):
        """Record a cache miss."""
        self.increment_counter('misses')

    def record_cache_set(self, duration_ms: float = 0.0):
        """Record a cache set operation."""
        self.increment_counter('sets')
        if duration_ms > 0:
            self.record_histogram('set_duration_ms', duration_ms)

    def record_cache_delete(self):
        """Record a cache delete operation."""
        self.increment_counter('deletes')

    def get_hit_rate(self) -> float:
        """Get cache hit rate."""
        return self.calculate_hit_rate('hits', 'misses')

    def get_cache_summary(self) -> Dict[str, Any]:
        """Get cache-specific summary."""
        base_summary = self.get_summary()
        base_summary['hit_rate'] = self.get_hit_rate()
        base_summary['total_requests'] = base_summary['counters'].get('hits', 0) + base_summary['counters'].get('misses', 0)
        return base_summary


class OccupancyMetricsCollector(MetricsCollector):
    """Specialized metrics for occupancy/inventory."""

    def set_total_capacity(self, capacity: int):
        """Set total capacity."""
        self.set_gauge('total_capacity', float(capacity))

    def set_occupied_count(self, occupied: int):
        """Set currently occupied count."""
        self.set_gauge('occupied_count', float(occupied))

    def get_occupancy_rate(self) -> float:
        """Get current occupancy rate (0.0 to 1.0)."""
        total = self.get_gauge('total_capacity')
        occupied = self.get_gauge('occupied_count')
        return occupied / total if total > 0 else 0.0

    def get_available_count(self) -> int:
        """Get available count."""
        total = int(self.get_gauge('total_capacity'))
        occupied = int(self.get_gauge('occupied_count'))
        return total - occupied

    def record_allocation(self, seats_allocated: int):
        """Record a seat allocation."""
        self.increment_counter('allocations')
        self.increment_gauge('occupied_count', float(seats_allocated))

    def record_cancellation(self, seats_freed: int):
        """Record a cancellation."""
        self.increment_counter('cancellations')
        self.decrement_gauge('occupied_count', float(seats_freed))

    def get_occupancy_summary(self) -> Dict[str, Any]:
        """Get occupancy-specific summary."""
        base_summary = self.get_summary()
        base_summary['occupancy_rate'] = self.get_occupancy_rate()
        base_summary['available_count'] = self.get_available_count()
        return base_summary


class PerformanceMetricsCollector(MetricsCollector):
    """Specialized metrics for operation performance."""

    def record_operation_duration(self, operation: str, duration_ms: float):
        """Record operation duration."""
        self.increment_counter(f'{operation}_count')
        self.record_histogram(f'{operation}_duration_ms', duration_ms)

    def record_operation_error(self, operation: str):
        """Record operation error."""
        self.increment_counter(f'{operation}_errors')

    def get_operation_performance(self, operation: str) -> Dict[str, Any]:
        """Get performance stats for an operation."""
        count = self.get_counter(f'{operation}_count')
        errors = self.get_counter(f'{operation}_errors')
        duration_stats = self.get_histogram_stats(f'{operation}_duration_ms')

        return {
            'operation': operation,
            'count': count,
            'errors': errors,
            'error_rate': errors / count if count > 0 else 0.0,
            'duration_stats': duration_stats,
        }

    def get_all_performance_summary(self) -> Dict[str, Any]:
        """Get summary of all operations."""
        summary = super().get_summary()

        # Extract unique operations
        operations = set()
        for counter_name in self.counters:
            if counter_name.endswith('_count'):
                op = counter_name[:-len('_count')]
                operations.add(op)

        performance_data = {}
        for op in operations:
            performance_data[op] = self.get_operation_performance(op)

        summary['operations'] = performance_data
        return summary
