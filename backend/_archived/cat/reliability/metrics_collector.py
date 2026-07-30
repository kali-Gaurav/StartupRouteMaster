"""
Metrics collection utilities for the Contextual Availability Transformer (CAT) system.
Provides Prometheus-compatible metrics collection and export.
"""

import logging
import time
import threading
from datetime import datetime
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, field
from collections import defaultdict
import statistics

logger = logging.getLogger(__name__)


@dataclass
class MetricPoint:
    """A single metric data point."""
    timestamp: datetime
    value: float
    labels: Dict[str, str] = field(default_factory=dict)


@dataclass
class Metric:
    """A metric with its data points."""
    name: str
    description: str
    metric_type: str  # counter, gauge, histogram
    unit: str = ""
    data_points: List[MetricPoint] = field(default_factory=list)
    labels: Dict[str, str] = field(default_factory=dict)
    
    def add_point(self, value: float, labels: Dict[str, str] = None) -> None:
        """Add a data point to the metric."""
        point = MetricPoint(
            timestamp=datetime.utcnow(),
            value=value,
            labels=labels or {}
        )
        self.data_points.append(point)
    
    def to_prometheus(self) -> str:
        """Export metric in Prometheus format."""
        lines = []
        
        # Help line
        lines.append(f"# HELP {self.name} {self.description}")
        
        # Type line
        lines.append(f"# TYPE {self.name} {self.metric_type}")
        
        # Data points
        for point in self.data_points:
            label_str = ",".join(f'{k}="{v}"' for k, v in {**self.labels, **point.labels}.items())
            if label_str:
                label_str = "{" + label_str + "}"
            lines.append(f"{self.name}{label_str} {point.value}")
        
        return "\n".join(lines)


class MetricsCollector:
    """
    Metrics collector for CAT system.
    
    Collects inference latency, request rates, error rates, and cache metrics.
    Exports metrics in Prometheus format.
    """
    
    def __init__(self, export_interval_seconds: int = 60):
        """
        Initialize the metrics collector.
        
        Args:
            export_interval_seconds: Interval for exporting metrics
        """
        self._metrics: Dict[str, Metric] = {}
        self._lock = threading.Lock()
        self._export_interval = export_interval_seconds
        self._start_time = datetime.utcnow()
        
        # Initialize default metrics
        self._init_default_metrics()
    
    def _init_default_metrics(self) -> None:
        """Initialize default metrics."""
        # Inference latency (histogram)
        self._create_metric(
            name="cat_inference_latency_seconds",
            description="Inference latency in seconds",
            metric_type="histogram",
            unit="seconds"
        )
        
        # Request rate (counter)
        self._create_metric(
            name="cat_requests_total",
            description="Total number of requests",
            metric_type="counter",
            unit="requests"
        )
        
        # Error rate (counter)
        self._create_metric(
            name="cat_errors_total",
            description="Total number of errors",
            metric_type="counter",
            unit="errors"
        )
        
        # Cache hit/miss (counter)
        self._create_metric(
            name="cat_cache_hits_total",
            description="Total number of cache hits",
            metric_type="counter",
            unit="hits"
        )
        
        self._create_metric(
            name="cat_cache_misses_total",
            description="Total number of cache misses",
            metric_type="counter",
            unit="misses"
        )
        
        # Model loading status (gauge)
        self._create_metric(
            name="cat_model_loaded",
            description="Model loading status (1=loaded, 0=not loaded)",
            metric_type="gauge",
            unit="status"
        )
        
        # Data freshness (gauge)
        self._create_metric(
            name="cat_data_freshness_seconds",
            description="Data freshness in seconds",
            metric_type="gauge",
            unit="seconds"
        )
    
    def _create_metric(
        self,
        name: str,
        description: str,
        metric_type: str,
        unit: str = ""
    ) -> Metric:
        """Create a new metric."""
        with self._lock:
            if name not in self._metrics:
                self._metrics[name] = Metric(
                    name=name,
                    description=description,
                    metric_type=metric_type,
                    unit=unit
                )
            return self._metrics[name]
    
    def record_inference_latency(self, latency_seconds: float, labels: Dict[str, str] = None) -> None:
        """
        Record inference latency.
        
        Args:
            latency_seconds: Inference latency in seconds
            labels: Optional labels for the metric
        """
        metric = self._create_metric(
            "cat_inference_latency_seconds",
            "Inference latency in seconds",
            "histogram"
        )
        metric.add_point(latency_seconds, labels)
    
    def record_request(self, labels: Dict[str, str] = None) -> None:
        """
        Record a request.
        
        Args:
            labels: Optional labels for the metric
        """
        metric = self._create_metric(
            "cat_requests_total",
            "Total number of requests",
            "counter"
        )
        metric.add_point(1, labels)
    
    def record_error(self, labels: Dict[str, str] = None) -> None:
        """
        Record an error.
        
        Args:
            labels: Optional labels for the metric
        """
        metric = self._create_metric(
            "cat_errors_total",
            "Total number of errors",
            "counter"
        )
        metric.add_point(1, labels)
    
    def record_cache_hit(self, labels: Dict[str, str] = None) -> None:
        """
        Record a cache hit.
        
        Args:
            labels: Optional labels for the metric
        """
        metric = self._create_metric(
            "cat_cache_hits_total",
            "Total number of cache hits",
            "counter"
        )
        metric.add_point(1, labels)
    
    def record_cache_miss(self, labels: Dict[str, str] = None) -> None:
        """
        Record a cache miss.
        
        Args:
            labels: Optional labels for the metric
        """
        metric = self._create_metric(
            "cat_cache_misses_total",
            "Total number of cache misses",
            "counter"
        )
        metric.add_point(1, labels)
    
    def set_model_loaded(self, loaded: bool) -> None:
        """
        Set model loading status.
        
        Args:
            loaded: True if model is loaded
        """
        metric = self._create_metric(
            "cat_model_loaded",
            "Model loading status (1=loaded, 0=not loaded)",
            "gauge"
        )
        value = 1.0 if loaded else 0.0
        metric.add_point(value)
    
    def set_data_freshness(self, freshness_seconds: float) -> None:
        """
        Set data freshness.
        
        Args:
            freshness_seconds: Data freshness in seconds
        """
        metric = self._create_metric(
            "cat_data_freshness_seconds",
            "Data freshness in seconds",
            "gauge"
        )
        metric.add_point(freshness_seconds)
    
    def get_latency_percentiles(self) -> Dict[str, float]:
        """
        Get latency percentiles (p50, p95, p99).
        
        Returns:
            Dictionary with p50, p95, p99 latency values
        """
        metric = self._metrics.get("cat_inference_latency_seconds")
        if not metric or not metric.data_points:
            return {"p50": 0.0, "p95": 0.0, "p99": 0.0}
        
        values = [p.value for p in metric.data_points]
        if not values:
            return {"p50": 0.0, "p95": 0.0, "p99": 0.0}
        
        values.sort()
        n = len(values)
        
        return {
            "p50": values[int(n * 0.50)],
            "p95": values[int(n * 0.95)],
            "p99": values[int(n * 0.99)]
        }
    
    def get_request_rate(self) -> float:
        """
        Get request rate (requests per second).
        
        Returns:
            Request rate in requests per second
        """
        metric = self._metrics.get("cat_requests_total")
        if not metric or not metric.data_points:
            return 0.0
        
        elapsed = (datetime.utcnow() - self._start_time).total_seconds()
        if elapsed <= 0:
            return 0.0
        
        return len(metric.data_points) / elapsed
    
    def get_error_rate(self) -> float:
        """
        Get error rate (errors per request).
        
        Returns:
            Error rate as a percentage
        """
        requests_metric = self._metrics.get("cat_requests_total")
        errors_metric = self._metrics.get("cat_errors_total")
        
        if not requests_metric or not requests_metric.data_points:
            return 0.0
        
        request_count = len(requests_metric.data_points)
        error_count = len(errors_metric.data_points) if errors_metric else 0
        
        return (error_count / request_count) * 100
    
    def get_cache_stats(self) -> Dict[str, int]:
        """
        Get cache hit/miss statistics.
        
        Returns:
            Dictionary with cache_hits and cache_misses counts
        """
        hits = len(self._metrics.get("cat_cache_hits_total", Metric("", "", "counter")).data_points)
        misses = len(self._metrics.get("cat_cache_misses_total", Metric("", "", "counter")).data_points)
        
        return {
            "cache_hits": hits,
            "cache_misses": misses,
            "cache_hit_rate": hits / (hits + misses) if (hits + misses) > 0 else 0.0
        }
    
    def export_prometheus(self) -> str:
        """
        Export all metrics in Prometheus format.
        
        Returns:
            Prometheus-formatted metrics string
        """
        lines = []
        lines.append(f"# CAT Metrics Export - {datetime.utcnow().isoformat()}")
        lines.append("")
        
        with self._lock:
            for metric in self._metrics.values():
                lines.append(metric.to_prometheus())
                lines.append("")
        
        return "\n".join(lines)
    
    def get_summary(self) -> Dict[str, Any]:
        """
        Get a summary of all metrics.
        
        Returns:
            Dictionary with metric summaries
        """
        return {
            "uptime_seconds": (datetime.utcnow() - self._start_time).total_seconds(),
            "request_rate": self.get_request_rate(),
            "error_rate": self.get_error_rate(),
            "latency_percentiles": self.get_latency_percentiles(),
            "cache_stats": self.get_cache_stats(),
            "model_loaded": self._metrics.get("cat_model_loaded", Metric("", "", "gauge")).data_points[-1].value if self._metrics.get("cat_model_loaded", Metric("", "", "gauge")).data_points else 0.0
        }


def create_metrics_collector() -> MetricsCollector:
    """
    Factory function to create a MetricsCollector.
    
    Returns:
        Configured MetricsCollector instance
    """
    return MetricsCollector()
