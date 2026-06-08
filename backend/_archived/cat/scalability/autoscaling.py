"""
Autoscaling configuration for the Contextual Availability Transformer (CAT) system.

Implements Kubernetes autoscaling configuration and scaling metrics.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ScalingMetrics:
    """
    Metrics for autoscaling decisions.
    
    Tracks request rate, latency, and queue depth.
    """
    request_rate: float = 0.0  # Requests per second
    p50_latency: float = 0.0  # 50th percentile latency in seconds
    p95_latency: float = 0.0  # 95th percentile latency in seconds
    p99_latency: float = 0.0  # 99th percentile latency in seconds
    queue_depth: int = 0  # Number of requests in queue
    cpu_utilization: float = 0.0  # CPU utilization percentage
    memory_utilization: float = 0.0  # Memory utilization percentage
    gpu_utilization: float = 0.0  # GPU utilization percentage
    timestamp: datetime = field(default_factory=datetime.utcnow)
    
    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary."""
        return {
            "request_rate": self.request_rate,
            "p50_latency": self.p50_latency,
            "p95_latency": self.p95_latency,
            "p99_latency": self.p99_latency,
            "queue_depth": self.queue_depth,
            "cpu_utilization": self.cpu_utilization,
            "memory_utilization": self.memory_utilization,
            "gpu_utilization": self.gpu_utilization,
            "timestamp": self.timestamp.isoformat()
        }


@dataclass
class AutoscalingConfig:
    """
    Configuration for autoscaling.
    
    Defines scaling thresholds and limits.
    """
    # Scaling thresholds
    min_replicas: int = 2
    max_replicas: int = 10
    target_request_rate: float = 100.0  # Target requests per second per replica
    target_p95_latency: float = 0.150  # Target P95 latency in seconds
    target_queue_depth: int = 10  # Target queue depth
    target_cpu_utilization: float = 70.0  # Target CPU utilization percentage
    target_memory_utilization: float = 80.0  # Target memory utilization percentage
    
    # Scaling behavior
    scale_up_cooldown: int = 30  # Seconds before scaling up again
    scale_down_cooldown: int = 180  # Seconds before scaling down again
    scale_up_factor: float = 1.5  # Factor to multiply replica count on scale up
    scale_down_factor: float = 0.75  # Factor to multiply replica count on scale down
    
    # Resource limits
    cpu_request: str = "500m"  # CPU request per replica
    cpu_limit: str = "1000m"  # CPU limit per replica
    memory_request: str = "1Gi"  # Memory request per replica
    memory_limit: str = "2Gi"  # Memory limit per replica
    gpu_request: str = "1"  # GPU request per replica (if applicable)
    
    # Metrics collection
    metrics_collection_interval: int = 10  # Seconds between metric collections


class KubernetesAutoscaler:
    """
    Manages Kubernetes autoscaling configuration.
    
    Provides scaling recommendations based on metrics.
    """
    
    def __init__(self, config: AutoscalingConfig = None):
        """
        Initialize the Kubernetes autoscaler.
        
        Args:
            config: Autoscaling configuration
        """
        self.config = config or AutoscalingConfig()
        self._current_replicas: int = self.config.min_replicas
        self._last_scale_up: float = 0.0
        self._last_scale_down: float = 0.0
        self._metrics_history: List[ScalingMetrics] = []
        self._history_size: int = 100  # Keep last 100 metric samples
    
    def update_metrics(self, metrics: ScalingMetrics) -> None:
        """
        Update metrics and potentially trigger scaling.
        
        Args:
            metrics: Current scaling metrics
        """
        # Add to history
        self._metrics_history.append(metrics)
        
        # Trim history
        if len(self._metrics_history) > self._history_size:
            self._metrics_history.pop(0)
        
        # Check if scaling is needed
        current_time = metrics.timestamp.timestamp()
        
        # Check for scale up
        if (current_time - self._last_scale_up > self.config.scale_up_cooldown and
            self._should_scale_up(metrics)):
            self._scale_up()
        
        # Check for scale down
        elif (current_time - self._last_scale_down > self.config.scale_down_cooldown and
              self._should_scale_down(metrics)):
            self._scale_down()
    
    def _should_scale_up(self, metrics: ScalingMetrics) -> bool:
        """
        Determine if scaling up is needed.
        
        Args:
            metrics: Current scaling metrics
            
        Returns:
            True if scaling up is recommended
        """
        # Check request rate
        if metrics.request_rate > self.config.target_request_rate * self._current_replicas:
            return True
        
        # Check latency
        if metrics.p95_latency > self.config.target_p95_latency:
            return True
        
        # Check queue depth
        if metrics.queue_depth > self.config.target_queue_depth:
            return True
        
        # Check CPU utilization
        if metrics.cpu_utilization > self.config.target_cpu_utilization:
            return True
        
        # Check memory utilization
        if metrics.memory_utilization > self.config.target_memory_utilization:
            return True
        
        return False
    
    def _should_scale_down(self, metrics: ScalingMetrics) -> bool:
        """
        Determine if scaling down is needed.
        
        Args:
            metrics: Current scaling metrics
            
        Returns:
            True if scaling down is recommended
        """
        # Check if we're below minimum replicas
        if self._current_replicas <= self.config.min_replicas:
            return False
        
        # Check request rate
        if metrics.request_rate < self.config.target_request_rate * self._current_replicas * 0.5:
            return True
        
        # Check latency
        if metrics.p95_latency < self.config.target_p95_latency * 0.5:
            return True
        
        # Check queue depth
        if metrics.queue_depth < self.config.target_queue_depth * 0.5:
            return True
        
        # Check CPU utilization
        if metrics.cpu_utilization < self.config.target_cpu_utilization * 0.3:
            return True
        
        # Check memory utilization
        if metrics.memory_utilization < self.config.target_memory_utilization * 0.3:
            return True
        
        return False
    
    def _scale_up(self) -> None:
        """Scale up the number of replicas."""
        new_replicas = min(
            int(self._current_replicas * self.config.scale_up_factor),
            self.config.max_replicas
        )
        
        if new_replicas > self._current_replicas:
            logger.info(
                f"Scaling up from {self._current_replicas} to {new_replicas} replicas"
            )
            self._current_replicas = new_replicas
            self._last_scale_up = datetime.utcnow().timestamp()
    
    def _scale_down(self) -> None:
        """Scale down the number of replicas."""
        new_replicas = max(
            int(self._current_replicas * self.config.scale_down_factor),
            self.config.min_replicas
        )
        
        if new_replicas < self._current_replicas:
            logger.info(
                f"Scaling down from {self._current_replicas} to {new_replicas} replicas"
            )
            self._current_replicas = new_replicas
            self._last_scale_down = datetime.utcnow().timestamp()
    
    def get_replica_count(self) -> int:
        """
        Get the current recommended replica count.
        
        Returns:
            Recommended number of replicas
        """
        return self._current_replicas
    
    def get_scaling_recommendation(self, metrics: ScalingMetrics = None) -> Dict[str, Any]:
        """
        Get scaling recommendation based on current metrics.
        
        Args:
            metrics: Current scaling metrics (uses latest if None)
            
        Returns:
            Scaling recommendation
        """
        if metrics is None and self._metrics_history:
            metrics = self._metrics_history[-1]
        
        recommendation = {
            "current_replicas": self._current_replicas,
            "recommended_replicas": self._current_replicas,
            "action": "no_change",
            "metrics": metrics.to_dict() if metrics else None,
            "reasons": []
        }
        
        if metrics:
            reasons = []
            
            # Check request rate
            if metrics.request_rate > self.config.target_request_rate * self._current_replicas:
                reasons.append("High request rate")
                recommendation["action"] = "scale_up"
            
            # Check latency
            if metrics.p95_latency > self.config.target_p95_latency:
                reasons.append("High P95 latency")
                recommendation["action"] = "scale_up"
            
            # Check queue depth
            if metrics.queue_depth > self.config.target_queue_depth:
                reasons.append("High queue depth")
                recommendation["action"] = "scale_up"
            
            # Check CPU utilization
            if metrics.cpu_utilization > self.config.target_cpu_utilization:
                reasons.append("High CPU utilization")
                recommendation["action"] = "scale_up"
            
            # Check memory utilization
            if metrics.memory_utilization > self.config.target_memory_utilization:
                reasons.append("High memory utilization")
                recommendation["action"] = "scale_up"
            
            # Check for scale down
            if (recommendation["action"] == "no_change" and
                self._should_scale_down(metrics)):
                reasons.append("Low utilization")
                recommendation["action"] = "scale_down"
            
            recommendation["reasons"] = reasons
        
        return recommendation
    
    def get_kubernetes_hpa_spec(self) -> Dict[str, Any]:
        """
        Get Kubernetes HorizontalPodAutoscaler specification.
        
        Returns:
            HPA spec for deployment
        """
        return {
            "apiVersion": "autoscaling/v2",
            "kind": "HorizontalPodAutoscaler",
            "metadata": {
                "name": "cat-inference-service",
                "namespace": "default"
            },
            "spec": {
                "scaleTargetRef": {
                    "apiVersion": "apps/v1",
                    "kind": "Deployment",
                    "name": "cat-inference-service"
                },
                "minReplicas": self.config.min_replicas,
                "maxReplicas": self.config.max_replicas,
                "metrics": [
                    {
                        "type": "Resource",
                        "resource": {
                            "name": "cpu",
                            "target": {
                                "type": "Utilization",
                                "averageUtilization": int(self.config.target_cpu_utilization)
                            }
                        }
                    },
                    {
                        "type": "Resource",
                        "resource": {
                            "name": "memory",
                            "target": {
                                "type": "Utilization",
                                "averageUtilization": int(self.config.target_memory_utilization)
                            }
                        }
                    },
                    {
                        "type": "Pods",
                        "pods": {
                            "metric": {
                                "name": "cat_requests_per_second"
                            },
                            "target": {
                                "type": "AverageValue",
                                "averageValue": str(int(self.config.target_request_rate))
                            }
                        }
                    },
                    {
                        "type": "Pods",
                        "pods": {
                            "metric": {
                                "name": "cat_p95_latency"
                            },
                            "target": {
                                "type": "AverageValue",
                                "averageValue": str(self.config.target_p95_latency)
                            }
                        }
                    }
                ]
            }
        }
    
    def get_resource_requirements(self) -> Dict[str, Any]:
        """
        Get Kubernetes resource requirements for a single replica.
        
        Returns:
            Resource requirements
        """
        return {
            "requests": {
                "cpu": self.config.cpu_request,
                "memory": self.config.memory_request,
                "nvidia.com/gpu": self.config.gpu_request
            },
            "limits": {
                "cpu": self.config.cpu_limit,
                "memory": self.config.memory_limit,
                "nvidia.com/gpu": self.config.gpu_request
            }
        }
    
    def get_stats(self) -> Dict[str, Any]:
        """Get autoscaler statistics."""
        return {
            "current_replicas": self._current_replicas,
            "min_replicas": self.config.min_replicas,
            "max_replicas": self.config.max_replicas,
            "last_scale_up_seconds_ago": int(datetime.utcnow().timestamp() - self._last_scale_up),
            "last_scale_down_seconds_ago": int(datetime.utcnow().timestamp() - self._last_scale_down),
            "metrics_history_size": len(self._metrics_history)
        }


def create_autoscaler(config: AutoscalingConfig = None) -> KubernetesAutoscaler:
    """
    Factory function to create an autoscaler.
    
    Args:
        config: Autoscaling configuration
        
    Returns:
        Configured KubernetesAutoscaler instance
    """
    return KubernetesAutoscaler(config)
