"""
Scalability module for the Contextual Availability Transformer (CAT) system.

Provides horizontal scaling, autoscaling, and canary deployment utilities.
"""

from .horizontal_scaling import (
    StatelessInferenceService,
    ConnectionPoolConfig,
    ConnectionPool,
    create_connection_pool,
    GracefulShutdownManager
)

from .autoscaling import (
    AutoscalingConfig,
    KubernetesAutoscaler,
    ScalingMetrics,
    create_autoscaler
)

from .canary_deployment import (
    CanaryConfig,
    CanaryDeployment,
    TrafficSplitter,
    DeploymentMetrics,
    create_canary_deployment
)

__all__ = [
    # Horizontal scaling
    "StatelessInferenceService",
    "ConnectionPoolConfig",
    "ConnectionPool",
    "create_connection_pool",
    "GracefulShutdownManager",
    # Autoscaling
    "AutoscalingConfig",
    "KubernetesAutoscaler",
    "ScalingMetrics",
    "create_autoscaler",
    # Canary deployment
    "CanaryConfig",
    "CanaryDeployment",
    "TrafficSplitter",
    "DeploymentMetrics",
    "create_canary_deployment",
]
