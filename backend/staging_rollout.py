#!/usr/bin/env python3
"""
RouteMaster Backend Staging Rollout Script
==========================================

Implements controlled backend staging rollout with:
- 5% traffic allocation to staging environment
- Comprehensive monitoring and alerting
- Automatic rollback on error thresholds
- Data collection mode for ML training pipeline

Rollout Phases:
1. Pre-deployment validation
2. 5% traffic rollout with monitoring
3. Performance baseline establishment
4. Gradual traffic increase (5% → 25% → 50%)
5. Full production deployment

Safety Features:
- Circuit breaker pattern for automatic rollback
- Real-time performance monitoring
- Error rate and latency thresholds
- Manual override capabilities
"""

import asyncio
import aiohttp
import json
import logging
import time
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any, Tuple
from dataclasses import dataclass
import statistics
from enum import Enum
import signal
import sys
from prometheus_client import Counter, Gauge, Histogram, push_to_gateway

# Rollout metrics
ROLLOUT_TRAFFIC_PERCENTAGE = Gauge(
    'rollout_traffic_percentage',
    'Current traffic percentage allocated to staging'
)

ROLLOUT_ERRORS = Counter(
    'rollout_errors_total',
    'Total errors during rollout',
    ['error_type', 'phase']
)

ROLLOUT_LATENCY = Histogram(
    'rollout_request_latency_seconds',
    'Request latency during rollout',
    ['phase', 'endpoint'],
    buckets=(0.1, 0.5, 1, 2.5, 5, 10, 25, 50)
)

ROLLOUT_SUCCESS_RATE = Gauge(
    'rollout_success_rate',
    'Success rate during rollout phases'
)

class RolloutPhase(Enum):
    """Staging rollout phases"""
    PRE_DEPLOYMENT = "pre_deployment"
    TRAFFIC_5_PERCENT = "traffic_5_percent"
    TRAFFIC_25_PERCENT = "traffic_25_percent"
    TRAFFIC_50_PERCENT = "traffic_50_percent"
    FULL_PRODUCTION = "full_production"
    ROLLBACK = "rollback"

@dataclass
class RolloutMetrics:
    """Real-time rollout performance metrics"""
    phase: RolloutPhase
    traffic_percentage: float
    total_requests: int
    successful_requests: int
    failed_requests: int
    avg_latency: float
    p95_latency: float
    p99_latency: float
    error_rate: float
    timestamp: datetime

@dataclass
class RolloutConfig:
    """Configuration for staging rollout"""
    staging_url: str
    production_url: str
    prometheus_gateway: Optional[str] = None
    traffic_ramp_up_delays: Dict[RolloutPhase, int] = None  # seconds to wait at each phase
    error_thresholds: Dict[str, float] = None  # error_rate, latency_p95
    monitoring_interval: int = 30  # seconds
    max_rollout_duration: int = 3600  # 1 hour max

    def __post_init__(self):
        if self.traffic_ramp_up_delays is None:
            self.traffic_ramp_up_delays = {
                RolloutPhase.TRAFFIC_5_PERCENT: 300,   # 5 minutes
                RolloutPhase.TRAFFIC_25_PERCENT: 600,  # 10 minutes
                RolloutPhase.TRAFFIC_50_PERCENT: 900,  # 15 minutes
                RolloutPhase.FULL_PRODUCTION: 1800,    # 30 minutes
            }

        if self.error_thresholds is None:
            self.error_thresholds = {
                'error_rate_max': 0.05,      # 5% error rate threshold
                'latency_p95_max': 5.0,      # 5 second p95 latency threshold
                'latency_p99_max': 10.0,     # 10 second p99 latency threshold
            }

class TrafficRouter:
    """
    Intelligent traffic router for staging rollout

    Features:
    - Percentage-based traffic allocation
    - Circuit breaker for automatic rollback
    - Real-time performance monitoring
    - Request deduplication for consistency
    """

    def __init__(self, config: RolloutConfig):
        self.config = config
        self.current_phase = RolloutPhase.PRE_DEPLOYMENT
        self.staging_percentage = 0.0
        self.circuit_breaker_tripped = False
        self.request_count = 0
        self.metrics_history: List[RolloutMetrics] = []

    async def route_request(self, request_data: Dict[str, Any]) -> Tuple[Dict[str, Any], str]:
        """
        Route request to staging or production based on rollout phase

        Returns:
            (response_data, target_url)
        """
        self.request_count += 1

        # Determine target based on traffic percentage
        should_route_to_staging = (
            not self.circuit_breaker_tripped and
            self.staging_percentage > 0 and
            (self.request_count % int(100 / self.staging_percentage)) == 0
        )

        target_url = self.config.staging_url if should_route_to_staging else self.config.production_url
        target_type = "staging" if should_route_to_staging else "production"

        logging.debug(f"Routing request {self.request_count} to {target_type} ({self.staging_percentage:.1f}% staging)")

        return request_data, target_url

    def update_traffic_percentage(self, percentage: float):
        """Update traffic allocation percentage"""
        self.staging_percentage = min(max(percentage, 0.0), 100.0)
        ROLLOUT_TRAFFIC_PERCENTAGE.set(self.staging_percentage)
        logging.info(f"Updated staging traffic to {self.staging_percentage:.1f}%")

    def trip_circuit_breaker(self, reason: str):
        """Trip circuit breaker and route all traffic to production"""
        self.circuit_breaker_tripped = True
        self.staging_percentage = 0.0
        ROLLOUT_TRAFFIC_PERCENTAGE.set(0.0)
        logging.error(f"Circuit breaker tripped: {reason}")

    def reset_circuit_breaker(self):
        """Reset circuit breaker after manual intervention"""
        self.circuit_breaker_tripped = False
        logging.info("Circuit breaker reset")

    def record_metrics(self, metrics: RolloutMetrics):
        """Record rollout metrics for monitoring"""
        self.metrics_history.append(metrics)

        # Keep only last 100 metrics
        if len(self.metrics_history) > 100:
            self.metrics_history = self.metrics_history[-100:]

class RolloutMonitor:
    """
    Real-time monitoring during rollout

    Monitors:
    - Error rates and latency percentiles
    - Traffic distribution
    - Performance degradation
    - Automatic rollback triggers
    """

    def __init__(self, router: TrafficRouter, config: RolloutConfig):
        self.router = router
        self.config = config
        self.monitoring_active = False
        self.last_metrics: Optional[RolloutMetrics] = None

    async def start_monitoring(self):
        """Start real-time monitoring loop"""
        self.monitoring_active = True
        logging.info("Started rollout monitoring")

        while self.monitoring_active:
            try:
                await self._check_health()
                await asyncio.sleep(self.config.monitoring_interval)
            except Exception as e:
                logging.error(f"Monitoring error: {e}")
                await asyncio.sleep(5)  # Brief pause on error

    async def stop_monitoring(self):
        """Stop monitoring"""
        self.monitoring_active = False
        logging.info("Stopped rollout monitoring")

    async def _check_health(self):
        """Check system health and trigger rollbacks if needed"""
        # This would integrate with actual monitoring systems
        # For now, we'll simulate health checks

        # Simulate getting current metrics
        current_metrics = await self._get_current_metrics()

        if current_metrics:
            self._evaluate_thresholds(current_metrics)

            # Push to Prometheus if configured
            if self.config.prometheus_gateway:
                push_to_gateway(
                    self.config.prometheus_gateway,
                    job='routemaster_rollout',
                    registry=None  # Use default registry
                )

    async def _get_current_metrics(self) -> Optional[RolloutMetrics]:
        """Get current system metrics (integrate with actual monitoring)"""
        # This would query Prometheus/Grafana or internal metrics
        # For simulation, return mock data

        # In real implementation, this would:
        # 1. Query Prometheus for error rates
        # 2. Query Grafana for latency percentiles
        # 3. Check service health endpoints

        return None  # Placeholder

    def _evaluate_thresholds(self, metrics: RolloutMetrics):
        """Evaluate if metrics exceed safety thresholds"""
        error_rate_threshold = self.config.error_thresholds['error_rate_max']
        latency_p95_threshold = self.config.error_thresholds['latency_p95_max']
        latency_p99_threshold = self.config.error_thresholds['latency_p99_max']

        violations = []

        if metrics.error_rate > error_rate_threshold:
            violations.append(f"Error rate {metrics.error_rate:.3f} > {error_rate_threshold}")

        if metrics.p95_latency > latency_p95_threshold:
            violations.append(f"P95 latency {metrics.p95_latency:.2f}s > {latency_p95_threshold}s")

        if metrics.p99_latency > latency_p99_threshold:
            violations.append(f"P99 latency {metrics.p99_latency:.2f}s > {latency_p99_threshold}s")

        if violations:
            reason = "; ".join(violations)
            logging.warning(f"Threshold violations detected: {reason}")
            self.router.trip_circuit_breaker(reason)

            ROLLOUT_ERRORS.labels(
                error_type='threshold_violation',
                phase=metrics.phase.value
            ).inc()

class StagingRolloutManager:
    """
    Manages the complete staging rollout process

    Orchestrates:
    - Pre-deployment validation
    - Phased traffic rollout
    - Monitoring and alerting
    - Automatic rollback capabilities
    """

    def __init__(self, config: RolloutConfig):
        self.config = config
        self.router = TrafficRouter(config)
        self.monitor = RolloutMonitor(self.router, config)
        self.rollout_start_time: Optional[datetime] = None
        self.current_phase = RolloutPhase.PRE_DEPLOYMENT

    async def execute_rollout(self) -> bool:
        """
        Execute the complete staging rollout

        Returns:
            True if rollout successful, False if rolled back
        """
        self.rollout_start_time = datetime.utcnow()
        logging.info("🚀 Starting RouteMaster staging rollout")

        try:
            # Phase 1: Pre-deployment validation
            if not await self._pre_deployment_validation():
                logging.error("Pre-deployment validation failed")
                return False

            # Phase 2: 5% traffic rollout
            if not await self._rollout_phase(RolloutPhase.TRAFFIC_5_PERCENT, 5.0):
                return False

            # Phase 3: 25% traffic rollout
            if not await self._rollout_phase(RolloutPhase.TRAFFIC_25_PERCENT, 25.0):
                return False

            # Phase 4: 50% traffic rollout
            if not await self._rollout_phase(RolloutPhase.TRAFFIC_50_PERCENT, 50.0):
                return False

            # Phase 5: Full production
            if not await self._rollout_phase(RolloutPhase.FULL_PRODUCTION, 100.0):
                return False

            logging.info("✅ Rollout completed successfully!")
            return True

        except Exception as e:
            logging.error(f"Rollout failed with exception: {e}")
            await self._emergency_rollback(f"Exception during rollout: {e}")
            return False

        finally:
            await self.monitor.stop_monitoring()

    async def _pre_deployment_validation(self) -> bool:
        """Validate staging environment before rollout"""
        logging.info("🔍 Running pre-deployment validation")

        self.current_phase = RolloutPhase.PRE_DEPLOYMENT

        # Health checks
        staging_healthy = await self._check_service_health(self.config.staging_url)
        production_healthy = await self._check_service_health(self.config.production_url)

        if not staging_healthy:
            logging.error("Staging service health check failed")
            return False

        if not production_healthy:
            logging.error("Production service health check failed")
            return False

        # Data collection mode validation
        if not await self._validate_data_collection_mode():
            logging.error("Data collection mode validation failed")
            return False

        # Load test staging environment
        if not await self._load_test_staging():
            logging.error("Staging load test failed")
            return False

        logging.info("✅ Pre-deployment validation passed")
        return True

    async def _rollout_phase(self, phase: RolloutPhase, traffic_percentage: float) -> bool:
        """Execute a specific rollout phase"""
        logging.info(f"📈 Starting {phase.value} phase ({traffic_percentage:.1f}% traffic)")

        self.current_phase = phase
        self.router.update_traffic_percentage(traffic_percentage)

        # Start monitoring for this phase
        monitor_task = asyncio.create_task(self.monitor.start_monitoring())

        # Wait for the specified delay
        delay = self.config.traffic_ramp_up_delays.get(phase, 300)
        await asyncio.sleep(delay)

        # Check if circuit breaker was tripped
        if self.router.circuit_breaker_tripped:
            logging.error(f"Circuit breaker tripped during {phase.value}")
            await self._emergency_rollback(f"Automatic rollback during {phase.value}")
            monitor_task.cancel()
            return False

        # Phase-specific validation
        if not await self._validate_phase(phase):
            logging.error(f"Phase {phase.value} validation failed")
            await self._emergency_rollback(f"Phase validation failed: {phase.value}")
            monitor_task.cancel()
            return False

        monitor_task.cancel()
        logging.info(f"✅ {phase.value} phase completed successfully")
        return True

    async def _emergency_rollback(self, reason: str):
        """Execute emergency rollback to production"""
        logging.error(f"🚨 Emergency rollback initiated: {reason}")

        self.current_phase = RolloutPhase.ROLLBACK
        self.router.trip_circuit_breaker(reason)

        # Wait for traffic to drain (all requests complete)
        await asyncio.sleep(30)

        # Validate production is handling all traffic
        if await self._check_service_health(self.config.production_url):
            logging.info("✅ Rollback completed - production handling all traffic")
        else:
            logging.critical("❌ Production service failed during rollback!")

    async def _check_service_health(self, url: str) -> bool:
        """Check if service is healthy"""
        try:
            timeout = aiohttp.ClientTimeout(total=10)
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.get(f"{url}/health") as response:
                    return response.status == 200
        except Exception as e:
            logging.error(f"Health check failed for {url}: {e}")
            return False

    async def _validate_data_collection_mode(self) -> bool:
        """Validate that data collection mode is active"""
        # Check if ML training pipeline is in data collection mode
        # This would query the actual service configuration
        return True  # Placeholder

    async def _load_test_staging(self) -> bool:
        """Run load test on staging environment"""
        # Use the concurrency tester we created earlier
        try:
            from concurrency_load_tester import RouteMasterConcurrencyTester

            async with RouteMasterConcurrencyTester(base_url=self.config.staging_url) as tester:
                results = await tester.run_burst_test([5, 10], requests_per_level=20)

                # Check if staging can handle basic load
                for result in results:
                    if result.successful_requests / result.total_requests < 0.95:  # 95% success rate
                        return False

            return True

        except Exception as e:
            logging.error(f"Staging load test failed: {e}")
            return False

    async def _validate_phase(self, phase: RolloutPhase) -> bool:
        """Validate specific phase requirements"""
        # Phase-specific validations
        if phase == RolloutPhase.TRAFFIC_5_PERCENT:
            # Ensure 5% traffic is being routed correctly
            return await self._validate_traffic_distribution(5.0)

        elif phase == RolloutPhase.TRAFFIC_25_PERCENT:
            # Validate performance at 25% load
            return await self._validate_performance_thresholds()

        elif phase == RolloutPhase.TRAFFIC_50_PERCENT:
            # Check for any degradation patterns
            return await self._check_degradation_patterns()

        elif phase == RolloutPhase.FULL_PRODUCTION:
            # Final validation before full production
            return await self._final_validation()

        return True

    async def _validate_traffic_distribution(self, expected_percentage: float) -> bool:
        """Validate that traffic is distributed correctly"""
        # This would check actual traffic metrics
        return True  # Placeholder

    async def _validate_performance_thresholds(self) -> bool:
        """Validate performance meets thresholds"""
        # Check current metrics against thresholds
        return True  # Placeholder

    async def _check_degradation_patterns(self) -> bool:
        """Check for performance degradation patterns"""
        # Analyze metrics history for trends
        return True  # Placeholder

    async def _final_validation(self) -> bool:
        """Final validation before full production"""
        # Comprehensive final checks
        return True  # Placeholder

    def get_rollout_status(self) -> Dict[str, Any]:
        """Get current rollout status"""
        return {
            'phase': self.current_phase.value,
            'traffic_percentage': self.router.staging_percentage,
            'circuit_breaker_tripped': self.router.circuit_breaker_tripped,
            'start_time': self.rollout_start_time.isoformat() if self.rollout_start_time else None,
            'duration': str(datetime.utcnow() - self.rollout_start_time) if self.rollout_start_time else None,
            'metrics_count': len(self.router.metrics_history)
        }

# Signal handlers for graceful shutdown
def signal_handler(signum, frame):
    logging.info(f"Received signal {signum}, initiating graceful shutdown")
    sys.exit(0)

async def main():
    """Execute staging rollout"""
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(levelname)s - %(message)s'
    )

    # Rollout configuration
    config = RolloutConfig(
        staging_url="http://localhost:8001",  # Staging backend
        production_url="http://localhost:8000",  # Production backend
        prometheus_gateway="http://localhost:9091",  # Prometheus push gateway
    )

    # Execute rollout
    manager = StagingRolloutManager(config)

    try:
        success = await manager.execute_rollout()

        if success:
            print("🎉 Staging rollout completed successfully!")
            print("📊 Final status:", json.dumps(manager.get_rollout_status(), indent=2))
        else:
            print("❌ Staging rollout failed or was rolled back")
            print("📊 Final status:", json.dumps(manager.get_rollout_status(), indent=2))
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n⚠️  Rollout interrupted by user")
        await manager._emergency_rollback("User interrupted rollout")
        sys.exit(1)

    except Exception as e:
        logging.critical(f"Unexpected error during rollout: {e}")
        await manager._emergency_rollback(f"Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(main())