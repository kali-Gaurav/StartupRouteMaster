# Route Engine Evolution - Circuit Breakers & Parallelization

**Owner:** SIGMA (Backend Lead)  
**Status:** 🔄 IN PROGRESS  
**Date:** 2026-05-08

---

## Overview

Implement circuit breakers and parallelization for the Tiered Intelligence Pipeline to ensure:
1. **Resilience:** Graceful degradation when services fail
2. **Performance:** Parallel execution of independent stages
3. **Reliability:** Automatic recovery from failures

---

## Circuit Breaker Pattern

### Implementation

```python
# backend/services/routing/circuit_breaker.py

import asyncio
import logging
from enum import Enum
from datetime import datetime, timedelta
from typing import Callable, Any, Optional
from dataclasses import dataclass

logger = logging.getLogger(__name__)

class CircuitState(Enum):
    """Circuit breaker states"""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing recovery


@dataclass
class CircuitConfig:
    """Circuit breaker configuration"""
    failure_threshold: int = 5          # Failures before opening
    success_threshold: int = 3          # Successes in half-open to close
    timeout_seconds: int = 30           # Time before trying again
    expected_exception: type = Exception


class CircuitBreaker:
    """
    Circuit breaker for pipeline stages.
    
    State Machine:
    CLOSED → (failure_threshold reached) → OPEN
    OPEN → (timeout_seconds passed) → HALF_OPEN
    HALF_OPEN → (success_threshold reached) → CLOSED
    HALF_OPEN → (any failure) → OPEN
    """
    
    def __init__(self, name: str, config: CircuitConfig = None):
        self.name = name
        self.config = config or CircuitConfig()
        self.state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: Optional[datetime] = None
        self._lock = asyncio.Lock()
    
    async def call(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute function with circuit breaker protection.
        
        Args:
            func: Async function to execute
            *args, **kwargs: Function arguments
            
        Returns:
            Function result
            
        Raises:
            CircuitOpenError: If circuit is open
            func's original exception: If function fails
        """
        async with self._lock:
            if self.state == CircuitState.OPEN:
                if self._should_attempt_reset():
                    self.state = CircuitState.HALF_OPEN
                    self.success_count = 0
                else:
                    raise CircuitOpenError(
                        f"Circuit {self.name} is OPEN. "
                        f"Retry after {self.config.timeout_seconds}s"
                    )
        
        # Execute function outside lock to avoid blocking
        try:
            result = await func(*args, **kwargs)
            await self._on_success()
            return result
            
        except self.config.expected_exception as e:
            await self._on_failure()
            raise
        except Exception as e:
            # Non-expected exceptions don't affect circuit
            logger.warning(f"{self.name}: Unexpected error: {e}")
            raise
    
    async def _on_success(self):
        """Handle successful execution"""
        async with self._lock:
            if self.state == CircuitState.HALF_OPEN:
                self.success_count += 1
                if self.success_count >= self.config.success_threshold:
                    self.state = CircuitState.CLOSED
                    self.failure_count = 0
                    logger.info(f"Circuit {self.name} CLOSED (recovered)")
            else:
                # Reset failure count on success in closed state
                self.failure_count = 0
    
    async def _on_failure(self):
        """Handle failed execution"""
        async with self._lock:
            self.failure_count += 1
            self.last_failure_time = datetime.utcnow()
            
            if self.state == CircuitState.HALF_OPEN:
                self.state = CircuitState.OPEN
                logger.warning(f"Circuit {self.name} OPEN (failed in half-open)")
            elif self.failure_count >= self.config.failure_threshold:
                self.state = CircuitState.OPEN
                logger.warning(
                    f"Circuit {self.name} OPEN "
                    f"({self.failure_count} failures)"
                )
    
    def _should_attempt_reset(self) -> bool:
        """Check if enough time has passed to try reset"""
        if self.last_failure_time is None:
            return True
        elapsed = datetime.utcnow() - self.last_failure_time
        return elapsed.total_seconds() >= self.config.timeout_seconds
    
    @property
    def status(self) -> dict:
        """Get circuit status for monitoring"""
        return {
            "name": self.name,
            "state": self.state.value,
            "failure_count": self.failure_count,
            "success_count": self.success_count,
            "last_failure": self.last_failure_time.isoformat() 
                if self.last_failure_time else None
        }


class CircuitOpenError(Exception):
    """Raised when circuit is open"""
    pass
```

---

## Pipeline with Circuit Breakers

```python
# backend/services/routing/unified_route_service.py

import asyncio
from typing import List, Optional
from datetime import datetime

from backend.services.routing.circuit_breaker import (
    CircuitBreaker, CircuitConfig, CircuitOpenError
)
from backend.services.routing.query_plan_optimizer import QueryPlanOptimizer
from backend.services.routing.transfer_intelligence import TransferIntelligenceService
from backend.services.routing.corridor_safety_bus import CorridorSafetyBus
from backend.services.route_engine import RouteEngine

class UnifiedRouteService:
    """
    Unified route service with circuit breakers and parallelization.
    
    Pipeline:
    ┌─────────┐     ┌─────────┐     ┌─────────┐     ┌─────────┐
    │   QPO   │────▶│  RAPTOR │────▶│   TIS   │────▶│ SAFETY  │
    └─────────┘     └─────────┘     └─────────┘     └─────────┘
         │               │               │               │
    [Circuit]      [Circuit]       [Circuit]       [Circuit]
    """
    
    def __init__(self):
        # Initialize circuit breakers for each stage
        self.qpo_circuit = CircuitBreaker(
            "qpo",
            CircuitConfig(failure_threshold=3, timeout_seconds=10)
        )
        self.raptor_circuit = CircuitBreaker(
            "raptor",
            CircuitConfig(failure_threshold=5, timeout_seconds=30)
        )
        self.tis_circuit = CircuitBreaker(
            "tis",
            CircuitConfig(failure_threshold=5, timeout_seconds=15)
        )
        self.safety_circuit = CircuitBreaker(
            "safety",
            CircuitConfig(failure_threshold=3, timeout_seconds=10)
        )
        
        # Initialize services
        self.route_engine = RouteEngine()
        self.optimizer = QueryPlanOptimizer(self.route_engine)
        self.tis_service = TransferIntelligenceService()
        self.safety_bus = CorridorSafetyBus()
    
    async def search_routes(
        self,
        request: UnifiedRouteRequest
    ) -> List[EnrichedRoute]:
        """
        Search routes with circuit breaker protection.
        
        Falls back to faster pipeline if circuit is open.
        """
        try:
            # Try full pipeline
            return await self._full_pipeline_search(request)
        except CircuitOpenError as e:
            logger.warning(f"Full pipeline failed: {e}")
            # Fallback: Skip TIS scoring for speed
            return await self._fast_pipeline_search(request)
    
    async def _full_pipeline_search(
        self,
        request: UnifiedRouteRequest
    ) -> List[EnrichedRoute]:
        """Full pipeline with all intelligence features"""
        
        # Stage 1: Query Plan Optimization
        plan = await self.qpo_circuit.call(
            self.optimizer.create_query_plan,
            QueryContext(
                source=request.source,
                destination=request.destination,
                travel_date=request.travel_date
            )
        )
        
        # Stage 2: Route Search (RAPTOR)
        routes = await self.raptor_circuit.call(
            self.route_engine.search_routes,
            request.source,
            request.destination,
            request.travel_date,
            max_routes=request.max_routes
        )
        
        # Stage 3: Transfer Intelligence Scoring
        scored_routes = []
        for route in routes:
            enriched = await self.tis_circuit.call(
                self._score_route_with_tis,
                route
            )
            scored_routes.append(enriched)
        
        # Stage 4: Safety Check
        safety_status = await self.safety_circuit.call(
            self.safety_bus.get_corridor_safety,
            request.source,
            request.destination
        )
        
        # Apply safety penalty
        for route in scored_routes:
            route.safety_score *= safety_status.safety_score
        
        return scored_routes
    
    async def _fast_pipeline_search(
        self,
        request: UnifiedRouteRequest
    ) -> List[EnrichedRoute]:
        """
        Fast pipeline without TIS scoring.
        Used when TIS circuit is open.
        """
        # Skip QPO, use defaults
        # Skip TIS scoring
        # Basic safety check only
        
        routes = await self.route_engine.search_routes(
            request.source,
            request.destination,
            request.travel_date,
            max_routes=request.max_routes
        )
        
        # Basic enrichment
        return [
            EnrichedRoute(
                journey=route,
                overall_score=70,  # Default score
                quality_score=70,
                safety_score=100,
                transfer_score=50,
                risk_level="unknown"
            )
            for route in routes
        ]
    
    async def _score_route_with_tis(self, route) -> EnrichedRoute:
        """Score a single route with TIS"""
        if len(route.segments) == 1:
            # Direct route, no transfers
            return EnrichedRoute(
                journey=route,
                overall_score=90,
                quality_score=90,
                safety_score=100,
                transfer_score=100,
                risk_level="low"
            )
        
        # Score transfers
        transfer_scores = []
        for i in range(len(route.segments) - 1):
            arrival = route.segments[i]
            departure = route.segments[i + 1]
            
            score = await self.tis_service.calculate_transfer_score(
                transfer_station=arrival.to_station_code,
                arrival_train=arrival.train_number,
                departure_train=departure.train_number,
                connection_time_minutes=30
            )
            transfer_scores.append(score.tis_score)
        
        avg_transfer_score = sum(transfer_scores) / len(transfer_scores)
        
        return EnrichedRoute(
            journey=route,
            overall_score=avg_transfer_score,
            quality_score=80,
            safety_score=100,
            transfer_score=avg_transfer_score,
            risk_level=self._calculate_risk(avg_transfer_score)
        )
    
    def _calculate_risk(self, score: float) -> str:
        """Calculate risk level from TIS score"""
        if score >= 80:
            return "low"
        elif score >= 60:
            return "medium"
        else:
            return "high"
    
    def get_circuit_status(self) -> dict:
        """Get status of all circuit breakers"""
        return {
            "qpo": self.qpo_circuit.status,
            "raptor": self.raptor_circuit.status,
            "tis": self.tis_circuit.status,
            "safety": self.safety_circuit.status
        }
```

---

## Parallelization

### Independent Stage Parallelization

```python
# backend/services/routing/parallel_pipeline.py

import asyncio
from typing import List, Dict, Any
from dataclasses import dataclass

@dataclass
class ParallelResult:
    """Result from parallel execution"""
    key: str
    value: Any
    duration_ms: float
    success: bool
    error: Optional[str] = None


class ParallelPipeline:
    """
    Execute independent pipeline stages in parallel.
    
    Example:
    ┌─────────────────┐     ┌─────────────────┐
    │  QPO (50ms)     │     │  Safety (30ms)  │
    │  Parallel       │     │  Parallel       │
    └────────┬────────┘     └────────┬────────┘
             │                       │
             └───────────┬───────────┘
                         ▼
              ┌─────────────────────┐
              │  Combine Results    │
              └─────────────────────┘
    """
    
    async def execute_parallel(
        self,
        tasks: Dict[str, asyncio.Task]
    ) -> Dict[str, ParallelResult]:
        """
        Execute tasks in parallel and return results.
        
        Args:
            tasks: Dict of name -> async task
            
        Returns:
            Dict of name -> ParallelResult
        """
        import time
        
        start_time = time.perf_counter()
        
        # Run all tasks concurrently
        results = {}
        
        # Wait for all tasks to complete
        for name, task in tasks.items():
            try:
                result = await task
                results[name] = ParallelResult(
                    key=name,
                    value=result,
                    duration_ms=(time.perf_counter() - start_time) * 1000,
                    success=True
                )
            except Exception as e:
                results[name] = ParallelResult(
                    key=name,
                    value=None,
                    duration_ms=(time.perf_counter() - start_time) * 1000,
                    success=False,
                    error=str(e)
                )
        
        return results
    
    async def execute_with_fallback(
        self,
        primary_task: asyncio.Task,
        fallback_task: asyncio.Task,
        timeout_seconds: float = 1.0
    ) -> Any:
        """
        Execute primary task with fallback if timeout.
        
        Args:
            primary_task: Primary async task
            fallback_task: Fallback async task
            timeout_seconds: Timeout for primary
            
        Returns:
            Primary result or fallback result
        """
        try:
            return await asyncio.wait_for(
                primary_task,
                timeout=timeout_seconds
            )
        except asyncio.TimeoutError:
            logger.warning("Primary task timed out, using fallback")
            return await fallback_task


# Usage in UnifiedRouteService
async def search_routes_parallel(
    self,
    request: UnifiedRouteRequest
) -> List[EnrichedRoute]:
    """Search routes with parallel execution"""
    
    parallel = ParallelPipeline()
    
    # Define independent tasks
    tasks = {
        "qpo": asyncio.create_task(self._run_qpo(request)),
        "safety": asyncio.create_task(
            self.safety_bus.get_corridor_safety(
                request.source,
                request.destination
            )
        )
    }
    
    # Execute in parallel
    results = await parallel.execute_parallel(tasks)
    
    # Get QPO plan
    qpo_plan = results["qpo"].value
    
    # Get safety status
    safety_status = results["safety"].value
    
    # Now run RAPTOR (depends on QPO)
    routes = await self.route_engine.search_routes(...)
    
    # Continue with TIS scoring (can be parallelized per route)
    scored_routes = await self._score_routes_parallel(routes)
    
    return scored_routes

async def _score_routes_parallel(
    self,
    routes: List[Journey]
) -> List[EnrichedRoute]:
    """Score multiple routes in parallel"""
    
    parallel = ParallelPipeline()
    
    # Create tasks for each route
    tasks = {
        f"route_{i}": asyncio.create_task(
            self._score_route_with_tis(route)
        )
        for i, route in enumerate(routes)
    }
    
    # Execute in parallel
    results = await parallel.execute_parallel(tasks)
    
    # Collect results in order
    scored_routes = []
    for i in range(len(routes)):
        result = results[f"route_{i}"]
        if result.success:
            scored_routes.append(result.value)
    
    return scored_routes
```

---

## Monitoring & Alerts

### Circuit Breaker Metrics

```python
# backend/services/routing/metrics.py

from prometheus_client import Counter, Histogram, Gauge

# Metrics
circuit_state = Gauge(
    'route_engine_circuit_state',
    'Circuit breaker state (0=closed, 1=half_open, 2=open)',
    ['circuit_name']
)

circuit_failures = Counter(
    'route_engine_circuit_failures_total',
    'Total circuit failures',
    ['circuit_name']
)

pipeline_duration = Histogram(
    'route_engine_pipeline_duration_ms',
    'Pipeline stage duration in ms',
    ['stage'],
    buckets=[10, 25, 50, 100, 250, 500, 1000, 2000]
)

fallback_usage = Counter(
    'route_engine_fallback_usage_total',
    'Total fallback usage count',
    ['fallback_type']
)

# Update metrics in circuit breaker
async def _on_failure(self):
    await super()._on_failure()
    circuit_state.labels(circuit_name=self.name).set(self.state.value)
    circuit_failures.labels(circuit_name=self.name).inc()
```

### Alert Rules

```yaml
# prometheus/alert-rules.yml

groups:
  - name: route-engine-circuit-breakers
    rules:
      - alert: CircuitBreakerOpen
        expr: route_engine_circuit_state > 1
        for: 1m
        labels:
          severity: critical
        annotations:
          summary: "Circuit breaker {{ $labels.circuit_name }} is OPEN"
          description: "Pipeline stage {{ $labels.circuit_name }} is failing"
      
      - alert: CircuitBreakerHalfOpen
        expr: route_engine_circuit_state == 1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Circuit breaker {{ $labels.circuit_name }} is HALF_OPEN"
          description: "Circuit may be recovering or unstable"
      
      - alert: PipelineLatencyHigh
        expr: histogram_quantile(0.95, rate(route_engine_pipeline_duration_ms[5m])) > 1000
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "Pipeline P95 latency > 1s"
          description: "Stage {{ $labels.stage }} is slow"
      
      - alert: FallbackHighUsage
        expr: rate(route_engine_fallback_usage_total[5m]) > 0.1
        for: 5m
        labels:
          severity: warning
        annotations:
          summary: "High fallback usage detected"
          description: "Fallback being used frequently"
```

---

## Action Items

| ID | Action | Owner | Status |
|----|--------|-------||--------|
| CB-01 | Implement CircuitBreaker class | SIGMA | ✅ DONE |
| CB-02 | Add circuit breakers to pipeline | SIGMA | ✅ DONE |
| CB-03 | Implement ParallelPipeline class | SIGMA | ✅ DONE |
| CB-04 | Add Prometheus metrics | SIGMA | 🔴 PENDING |
| CB-05 | Configure alert rules | SIGMA | 🔴 PENDING |
| CB-06 | Test circuit breaker behavior | SIGMA | 🔴 PENDING |
| CB-07 | Test parallel execution | SIGMA | 🔴 PENDING |

---

## Testing

```python
# tests/test_circuit_breaker.py

import pytest
import asyncio
from backend.services.routing.circuit_breaker import (
    CircuitBreaker, CircuitConfig, CircuitOpenError
)

class TestCircuitBreaker:
    """Tests for circuit breaker"""
    
    @pytest.fixture
    def circuit(self):
        """Create circuit breaker for testing"""
        return CircuitBreaker(
            "test",
            CircuitConfig(
                failure_threshold=3,
                success_threshold=2,
                timeout_seconds=1
            )
        )
    
    @pytest.mark.asyncio
    async def test_closed_state(self, circuit):
        """Test normal operation in closed state"""
        async def success():
            return "success"
        
        result = await circuit.call(success)
        assert result == "success"
        assert circuit.state.value == "closed"
        assert circuit.failure_count == 0
    
    @pytest.mark.asyncio
    async def test_opens_after_failures(self, circuit):
        """Test circuit opens after failure threshold"""
        async def fail():
            raise ValueError("fail")
        
        # Fail 3 times
        for _ in range(3):
            with pytest.raises(ValueError):
                await circuit.call(fail)
        
        assert circuit.state.value == "open"
    
    @pytest.mark.asyncio
    async def test_rejects_when_open(self, circuit):
        """Test requests are rejected when open"""
        circuit.state.value = "open"
        
        async def success():
            return "success"
        
        with pytest.raises(CircuitOpenError):
            await circuit.call(success)
    
    @pytest.mark.asyncio
    async def test_half_open_after_timeout(self, circuit):
        """Test circuit enters half-open after timeout"""
        circuit.state.value = "open"
        circuit.last_failure_time = datetime.utcnow() - timedelta(seconds=2)
        
        async def success():
            return "success"
        
        # Should not raise (circuit should be half-open)
        result = await circuit.call(success)
        assert result == "success"
        assert circuit.state.value == "closed"
```

---

**Document Version:** 1.0  
**Next Review:** 2026-05-15