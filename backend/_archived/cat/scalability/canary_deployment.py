"""
Canary deployment utilities for the Contextual Availability Transformer (CAT) system.

Implements traffic splitting and automatic rollback on error rate increase.
"""

import logging
import random
import time
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Callable, Dict, List, Optional
from enum import Enum

logger = logging.getLogger(__name__)


class CanaryStatus(Enum):
    """Status of the canary deployment."""
    NOT_STARTED = "not_started"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    ROLLED_BACK = "rolled_back"


@dataclass
class CanaryConfig:
    """
    Configuration for canary deployment.
    
    Defines traffic splitting and rollback thresholds.
    """
    # Traffic splitting
    initial_traffic_percentage: float = 10.0  # Start with 10% traffic to canary
    step_traffic_percentage: float = 10.0  # Increase by 10% per step
    max_traffic_percentage: float = 100.0  # Maximum traffic to canary
    
    # Rollback thresholds
    error_rate_threshold: float = 5.0  # Rollback if error rate exceeds 5%
    latency_threshold_ms: float = 250.0  # Rollback if P95 latency exceeds 250ms
    latency_threshold_factor: float = 1.5  # Rollback if latency is 1.5x baseline
    
    # Timing
    step_interval_seconds: int = 300  # Wait 5 minutes between steps
    health_check_interval_seconds: int = 10  # Check health every 10 seconds
    rollback_timeout_seconds: int = 60  # Timeout for rollback
    
    # Metrics
    min_requests_per_step: int = 100  # Minimum requests before evaluating step


@dataclass
class DeploymentMetrics:
    """Metrics for a single deployment."""
    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    total_latency_ms: float = 0.0
    latency_samples: List[float] = field(default_factory=list)
    error_rate: float = 0.0
    p95_latency_ms: float = 0.0
    last_updated: datetime = field(default_factory=datetime.utcnow)
    
    def record_request(self, success: bool, latency_ms: float) -> None:
        """Record a request."""
        self.total_requests += 1
        self.total_latency_ms += latency_ms
        
        if success:
            self.successful_requests += 1
        else:
            self.failed_requests += 1
        
        self.latency_samples.append(latency_ms)
        self.last_updated = datetime.utcnow()
        
        # Update error rate
        if self.total_requests > 0:
            self.error_rate = (self.failed_requests / self.total_requests) * 100
        
        # Update latency percentiles
        if self.latency_samples:
            sorted_latencies = sorted(self.latency_samples)
            p95_index = int(len(sorted_latencies) * 0.95)
            self.p95_latency_ms = sorted_latencies[min(p95_index, len(sorted_latencies) - 1)]
    
    def get_summary(self) -> Dict[str, Any]:
        """Get metrics summary."""
        return {
            "total_requests": self.total_requests,
            "successful_requests": self.successful_requests,
            "failed_requests": self.failed_requests,
            "error_rate": self.error_rate,
            "p95_latency_ms": self.p95_latency_ms,
            "avg_latency_ms": self.total_latency_ms / max(self.total_requests, 1),
            "last_updated": self.last_updated.isoformat()
        }


class TrafficSplitter:
    """
    Splits traffic between multiple deployment versions.
    
    Implements weighted routing based on traffic percentages.
    """
    
    def __init__(self, versions: List[str], weights: List[float]):
        """
        Initialize the traffic splitter.
        
        Args:
            versions: List of deployment versions
            weights: List of weights for each version (should sum to 1.0)
        """
        if len(versions) != len(weights):
            raise ValueError("Versions and weights must have the same length")
        
        if abs(sum(weights) - 1.0) > 0.001:
            raise ValueError("Weights must sum to 1.0")
        
        self.versions = versions
        self.weights = weights
        self._cumulative_weights = []
        
        # Calculate cumulative weights for efficient routing
        cumulative = 0.0
        for weight in weights:
            cumulative += weight
            self._cumulative_weights.append(cumulative)
    
    def route(self) -> str:
        """
        Route a request to a version based on weights.
        
        Returns:
            Selected version
        """
        rand = random.random()
        
        for i, cumulative in enumerate(self._cumulative_weights):
            if rand <= cumulative:
                return self.versions[i]
        
        # Fallback to last version
        return self.versions[-1]
    
    def update_weights(self, weights: List[float]) -> None:
        """
        Update traffic weights.
        
        Args:
            weights: New weights for each version
        """
        if abs(sum(weights) - 1.0) > 0.001:
            raise ValueError("Weights must sum to 1.0")
        
        self.weights = weights
        self._cumulative_weights = []
        
        cumulative = 0.0
        for weight in weights:
            cumulative += weight
            self._cumulative_weights.append(cumulative)


class CanaryDeployment:
    """
    Manages canary deployment with traffic splitting and automatic rollback.
    
    Implements progressive traffic shifting and health monitoring.
    """
    
    def __init__(self, config: CanaryConfig = None):
        """
        Initialize the canary deployment manager.
        
        Args:
            config: Canary deployment configuration
        """
        self.config = config or CanaryConfig()
        self._status = CanaryStatus.NOT_STARTED
        self._current_step = 0
        self._canary_traffic_percentage = 0.0
        self._baseline_metrics = DeploymentMetrics()
        self._canary_metrics = DeploymentMetrics()
        self._start_time: float = 0.0
        self._last_step_time: float = 0.0
        self._rollback_triggered = False
        self._rollback_reason: Optional[str] = None
    
    def start(self) -> None:
        """Start the canary deployment."""
        self._status = CanaryStatus.RUNNING
        self._start_time = time.time()
        self._last_step_time = self._start_time
        self._canary_traffic_percentage = self.config.initial_traffic_percentage
        
        logger.info(
            f"Canary deployment started: {self._canary_traffic_percentage}% traffic to canary"
        )
    
    def stop(self) -> None:
        """Stop the canary deployment."""
        self._status = CanaryStatus.SUCCEEDED
        logger.info("Canary deployment completed successfully")
    
    def fail(self, reason: str) -> None:
        """Mark the canary deployment as failed."""
        self._status = CanaryStatus.FAILED
        self._rollback_reason = reason
        logger.warning(f"Canary deployment failed: {reason}")
    
    def rollback(self, reason: str) -> None:
        """Trigger rollback of the canary deployment."""
        self._status = CanaryStatus.ROLLED_BACK
        self._rollback_triggered = True
        self._rollback_reason = reason
        logger.error(f"Canary deployment rolled back: {reason}")
    
    def should_route_to_canary(self) -> bool:
        """
        Determine if a request should be routed to the canary.
        
        Returns:
            True if request should go to canary
        """
        if self._status != CanaryStatus.RUNNING:
            return False
        
        return random.random() * 100 < self._canary_traffic_percentage
    
    def record_baseline_request(self, success: bool, latency_ms: float) -> None:
        """
        Record a request to the baseline deployment.
        
        Args:
            success: Whether the request succeeded
            latency_ms: Request latency in milliseconds
        """
        self._baseline_metrics.record_request(success, latency_ms)
    
    def record_canary_request(self, success: bool, latency_ms: float) -> None:
        """
        Record a request to the canary deployment.
        
        Args:
            success: Whether the request succeeded
            latency_ms: Request latency in milliseconds
        """
        self._canary_metrics.record_request(success, latency_ms)
    
    def should_evaluate_step(self) -> bool:
        """
        Determine if it's time to evaluate the canary step.
        
        Returns:
            True if step should be evaluated
        """
        if self._status != CanaryStatus.RUNNING:
            return False
        
        # Check if minimum requests have been made
        if (self._canary_metrics.total_requests < self.config.min_requests_per_step or
            self._baseline_metrics.total_requests < self.config.min_requests_per_step):
            return False
        
        # Check if enough time has passed since last step
        elapsed = time.time() - self._last_step_time
        return elapsed >= self.config.step_interval_seconds
    
    def evaluate_step(self) -> Dict[str, Any]:
        """
        Evaluate the current canary step and determine next action.
        
        Returns:
            Evaluation results
        """
        result = {
            "step": self._current_step,
            "canary_traffic_percentage": self._canary_traffic_percentage,
            "should_proceed": False,
            "should_rollback": False,
            "reasons": []
        }
        
        # Check error rates
        canary_error_rate = self._canary_metrics.error_rate
        baseline_error_rate = self._baseline_metrics.error_rate
        
        if canary_error_rate > self.config.error_rate_threshold:
            result["should_rollback"] = True
            result["reasons"].append(
                f"Canary error rate ({canary_error_rate:.1f}%) exceeds threshold "
                f"({self.config.error_rate_threshold}%)"
            )
        
        if canary_error_rate > baseline_error_rate * 2:
            result["should_rollback"] = True
            result["reasons"].append(
                f"Canary error rate is more than 2x baseline "
                f"({canary_error_rate:.1f}% vs {baseline_error_rate:.1f}%)"
            )
        
        # Check latency
        canary_p95_latency = self._canary_metrics.p95_latency_ms
        baseline_p95_latency = self._baseline_metrics.p95_latency_ms
        
        if canary_p95_latency > self.config.latency_threshold_ms:
            result["should_rollback"] = True
            result["reasons"].append(
                f"Canary P95 latency ({canary_p95_latency:.0f}ms) exceeds threshold "
                f"({self.config.latency_threshold_ms}ms)"
            )
        
        if baseline_p95_latency > 0 and (
            canary_p95_latency > baseline_p95_latency * self.config.latency_threshold_factor
        ):
            result["should_rollback"] = True
            result["reasons"].append(
                f"Canary P95 latency is {canary_p95_latency / baseline_p95_latency:.1f}x baseline "
                f"({canary_p95_latency:.0f}ms vs {baseline_p95_latency:.0f}ms)"
            )
        
        # If no rollback needed, consider proceeding to next step
        if not result["should_rollback"]:
            if self._canary_traffic_percentage < self.config.max_traffic_percentage:
                result["should_proceed"] = True
                self._current_step += 1
                self._canary_traffic_percentage = min(
                    self._canary_traffic_percentage + self.config.step_traffic_percentage,
                    self.config.max_traffic_percentage
                )
                self._last_step_time = time.time()
                
                result["reasons"].append(
                    f"Proceeding to next step: {self._canary_traffic_percentage}% traffic to canary"
                )
            else:
                result["should_proceed"] = False
                result["reasons"].append("Canary deployment complete")
                self._status = CanaryStatus.SUCCEEDED
        
        return result
    
    def get_traffic_split(self) -> Dict[str, float]:
        """
        Get current traffic split between deployments.
        
        Returns:
            Dictionary of version to traffic percentage
        """
        return {
            "baseline": 100.0 - self._canary_traffic_percentage,
            "canary": self._canary_traffic_percentage
        }
    
    def get_metrics(self) -> Dict[str, Any]:
        """
        Get deployment metrics.
        
        Returns:
            Dictionary of metrics for both deployments
        """
        return {
            "status": self._status.value,
            "current_step": self._current_step,
            "canary_traffic_percentage": self._canary_traffic_percentage,
            "baseline": self._baseline_metrics.get_summary(),
            "canary": self._canary_metrics.get_summary(),
            "rollback_triggered": self._rollback_triggered,
            "rollback_reason": self._rollback_reason,
            "uptime_seconds": int(time.time() - self._start_time) if self._start_time > 0 else 0
        }
    
    def get_traffic_splitter(self) -> TrafficSplitter:
        """
        Get the current traffic splitter.
        
        Returns:
            TrafficSplitter configured for current traffic split
        """
        return TrafficSplitter(
            versions=["baseline", "canary"],
            weights=[
                1.0 - (self._canary_traffic_percentage / 100.0),
                self._canary_traffic_percentage / 100.0
            ]
        )


def create_canary_deployment(config: CanaryConfig = None) -> CanaryDeployment:
    """
    Factory function to create a canary deployment manager.
    
    Args:
        config: Canary deployment configuration
        
    Returns:
        Configured CanaryDeployment instance
    """
    return CanaryDeployment(config)
