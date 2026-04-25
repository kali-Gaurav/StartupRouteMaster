# Agent System Specifications
## Patent-Level Travel Platform - Agent Orchestration Design

---

## Overview

This document defines the complete agent system for autonomous operation of the travel platform algorithm. Agents handle specific tasks like routing, pricing, allocation, and prediction, coordinated by an orchestration layer.

---

## Agent Categories

### 1. Routing Agents

#### RouteDiscoveryAgent
```yaml
name: RouteDiscoveryAgent
description: Discovers optimal routes using multiple algorithms
capabilities:
  - RAPTOR algorithm execution
  - TurboRouter binary search
  - TBR trip-based routing
  - Multi-modal route discovery
workflow:
  1. Classify request (direct/transfer/multi-modal)
  2. Select appropriate algorithm based on request type
  3. Execute search with constraints
  4. Apply real-time data
  5. Rank and return results
skills: ["raptor", "turbo_router", "tbr", "multimodal"]
```

#### RouteOptimizationAgent
```yaml
name: RouteOptimizationAgent
description: Optimizes discovered routes with constraints and preferences
capabilities:
  - Multi-criteria optimization
  - Constraint solving
  - Persona-based ranking
workflow:
  1. Apply user constraints (time, budget, class)
  2. Optimize for user persona
  3. Apply delay predictions
  4. Calculate total costs
  5. Generate alternatives
skills: ["constraint_solving", "multi_criteria_optimization", "persona_matching"]
```

#### MultiModalAgent
```yaml
name: MultiModalAgent
description: Handles multi-modal routing (train + bus + flight + cab)
capabilities:
  - Mode switching optimization
  - Intermodal routing
  - Cost-time tradeoff analysis
workflow:
  1. Parse multi-modal request
  2. Search each mode independently
  3. Find connection points
  4. Optimize mode switches
  5. Present combined options
skills: ["mode_switching", "intermodal", "cost_optimization"]
```

---

### 2. Pricing Agents

#### DynamicPricingAgent
```yaml
name: DynamicPricingAgent
description: Calculates optimal prices using demand data and surge pricing
capabilities:
  - Demand score calculation
  - Surge pricing application
  - Yield management
workflow:
  1. Calculate demand score from search volume
  2. Apply surge multiplier based on demand
  3. Apply yield adjustments
  4. Calculate final price with platform fee
  5. Return price breakdown
skills: ["demand_forecasting", "surge_pricing", "yield_management"]
```

#### CompetitivePricingAgent
```yaml
name: CompetitivePricingAgent
description: Monitors and responds to competitor pricing
capabilities:
  - Competitor price monitoring
  - Price position analysis
  - Dynamic adjustment
workflow:
  1. Fetch competitor prices (simulated)
  2. Calculate price position
  3. Adjust if needed for competitiveness
  4. Log pricing decisions
skills: ["market_analysis", "price_monitoring", "competitive_strategy"]
```

---

### 3. Allocation Agents

#### SeatAllocationAgent
```yaml
name: SeatAllocationAgent
description: Allocates seats to passengers with preference matching
capabilities:
  - Preference matching
  - Family grouping
  - Coach balancing
workflow:
  1. Get passenger preferences
  2. Match with available seats
  3. Group families together
  4. Balance coach distribution
  5. Return seat assignments
skills: ["preference_matching", "family_grouping", "coach_balancing"]
```

#### OverbookingAgent
```yaml
name: OverbookingAgent
description: Manages overbooking strategy based on cancellation predictions
capabilities:
  - Cancellation prediction
  - Risk calculation
  - Overbook limit determination
workflow:
  1. Get cancellation prediction
  2. Calculate risk level
  3. Determine overbook limit
  4. Monitor for confirmations
  5. Handle overflow
skills: ["cancellation_prediction", "risk_management", "optimization"]
```

---

### 4. Prediction Agents

#### DemandForecastAgent
```yaml
name: DemandForecastAgent
description: Predicts future demand for routes
capabilities:
  - Time series forecasting
  - Pattern recognition
  - Seasonal analysis
workflow:
  1. Collect historical data
  2. Apply forecasting model
  3. Generate predictions
  4. Update pricing system
skills: ["time_series", "pattern_recognition", "forecasting"]
```

#### DelayPredictionAgent
```yaml
name: DelayPredictionAgent
description: Predicts train delays for routing optimization
capabilities:
  - Historical delay analysis
  - Pattern matching
  - Weather correlation
workflow:
  1. Get historical delays for train
  2. Apply prediction model
  3. Return delay estimates with confidence
  4. Update route scores
skills: ["delay_analysis", "pattern_matching", "ml_prediction"]
```

#### CancellationPredictionAgent
```yaml
name: CancellationPredictionAgent
description: Predicts booking cancellations for overbooking strategy
capabilities:
  - User behavior analysis
  - Route-specific patterns
  - Survival analysis
workflow:
  1. Get booking features
  2. Apply cancellation model
  3. Return probability
  4. Update overbooking decisions
skills: ["survival_analysis", "user_behavior", "ml_prediction"]
```

---

### 5. Optimization Agents

#### RedistributionAgent
```yaml
name: RedistributionAgent
description: Redistributes passengers for network balance (Patent Innovation)
capabilities:
  - Network demand analysis
  - Opportunity identification
  - Incentive optimization
workflow:
  1. Analyze network demand
  2. Identify redistribution opportunities
  3. Calculate optimal incentives
  4. Offer to flexible passengers
  5. Track and optimize
skills: ["optimization", "incentive_design", "network_analysis"]
```

#### KnowledgeGraphAgent
```yaml
name: KnowledgeGraphAgent
description: Maintains and queries knowledge graph (Patent Innovation)
capabilities:
  - Graph updates
  - Pattern learning
  - Query execution
workflow:
  1. Update graph with new data
  2. Learn from interactions
  3. Answer queries
  4. Generate recommendations
skills: ["graph_queries", "knowledge_fusion", "recommendations"]
```

---

## Agent Orchestration

### Request Flow
```
User Request
    │
    ▼
┌─────────────────────────┐
│ Request Router Agent    │
│ • Classifies request    │
│ • Identifies agents     │
│ • Creates task graph    │
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│ Agent Coordinator       │
│ • Assigns tasks         │
│ • Manages dependencies  │
│ • Handles failures      │
└──────────┬──────────────┘
           │
    ┌──────┴──────┐
    │             │
    ▼             ▼
┌────────┐   ┌────────┐
│Routing │   │Pricing │
│Agents  │   │Agents  │
└───┬────┘   └───┬────┘
    │            │
    └──────┬─────┘
           │
           ▼
┌─────────────────────────┐
│ Output Aggregator       │
│ • Collects results      │
│ • Resolves conflicts    │
│ • Generates response    │
└─────────────────────────┘
```

### Agent Communication

```python
# Agent message format
{
    "message_id": "msg_123",
    "sender": "RouteDiscoveryAgent",
    "receiver": "DynamicPricingAgent",
    "action": "REQUEST_PRICING",
    "payload": {
        "routes": [...],
        "passengers": [...]
    },
    "correlation_id": "req_456",
    "reply_to": "pricing_response"
}

# Response format
{
    "message_id": "msg_789",
    "in_reply_to": "msg_123",
    "status": "SUCCESS",
    "payload": {
        "prices": [...]
    }
}
```

---

## Agent Configuration

### Agent Registry
```python
AGENT_REGISTRY = {
    "RouteDiscoveryAgent": {
        "class": "agents.routing.RouteDiscoveryAgent",
        "max_instances": 5,
        "timeout_seconds": 30,
        "retry_policy": "exponential_backoff",
        "capabilities": ["raptor", "turbo", "tbr"]
    },
    "DynamicPricingAgent": {
        "class": "agents.pricing.DynamicPricingAgent",
        "max_instances": 3,
        "timeout_seconds": 10,
        "retry_policy": "fixed",
        "capabilities": ["surge", "yield", "competitive"]
    },
    # ... other agents
}
```

### Skill Mapping
```python
SKILL_TO_AGENT = {
    "raptor": ["RouteDiscoveryAgent"],
    "turbo_router": ["RouteDiscoveryAgent"],
    "delay_prediction": ["DelayPredictionAgent", "RouteOptimizationAgent"],
    "surge_pricing": ["DynamicPricingAgent"],
    "seat_allocation": ["SeatAllocationAgent"],
    "cancellation_prediction": ["OverbookingAgent", "CancellationPredictionAgent"],
    "demand_forecasting": ["DemandForecastAgent", "DynamicPricingAgent"],
    "redistribution": ["RedistributionAgent"],
    "knowledge_graph": ["KnowledgeGraphAgent"],
}
```

---

## Error Handling

### Retry Policies
```python
RETRY_POLICIES = {
    "exponential_backoff": {
        "max_attempts": 3,
        "initial_delay": 1.0,
        "max_delay": 30.0,
        "multiplier": 2.0
    },
    "fixed": {
        "max_attempts": 2,
        "delay": 5.0
    },
    "circuit_breaker": {
        "failure_threshold": 5,
        "timeout_seconds": 60,
        "success_threshold": 3
    }
}
```

### Fallback Strategies
```python
FALLBACK_STRATEGIES = {
    "RouteDiscoveryAgent": {
        "primary": "raptor",
        "fallback": ["turbo_router", "tbr"],
        "default_response": []
    },
    "DynamicPricingAgent": {
        "primary": "ml_model",
        "fallback": "rule_based",
        "default_response": {"surge_multiplier": 1.0}
    }
}
```

---

## Monitoring & Metrics

### Agent Metrics
```python
AGENT_METRICS = {
    "requests_total": "Counter",
    "requests_success": "Counter", 
    "requests_failed": "Counter",
    "latency_seconds": "Histogram",
    "queue_depth": "Gauge",
    "active_agents": "Gauge",
    "retry_count": "Counter"
}
```

### Health Checks
```python
def health_check(agent_name: str) -> Dict:
    return {
        "agent": agent_name,
        "status": "healthy" | "degraded" | "down",
        "active_instances": int,
        "queue_depth": int,
        "avg_latency_ms": float,
        "error_rate": float
    }
```

---

## Usage Examples

### Direct Agent Usage
```python
from services.agents.registry import get_agent

# Get a specific agent
route_agent = get_agent("RouteDiscoveryAgent")

# Execute task
result = await route_agent.execute(
    action="find_routes",
    payload={
        "source": "NDLS",
        "destination": "BCT",
        "date": "2024-12-25",
        "constraints": {"max_transfers": 2}
    }
)
```

### Skill-Based Routing
```python
from services.agents.registry import find_agent_by_skill

# Find agent that can handle RAPTOR routing
agent = find_agent_by_skill("raptor")

# Or find all agents with a skill
agents = find_agents_by_skill("delay_prediction")
```

### Orchestrated Execution
```python
from services.agents.orchestrator import AgentOrchestrator

orchestrator = AgentOrchestrator()

# Execute complex workflow
result = await orchestrator.execute_workflow(
    workflow="booking_flow",
    context={
        "user_id": "user_123",
        "source": "NDLS",
        "destination": "BCT",
        "date": "2024-12-25",
        "passengers": 2
    }
)
```

---

## Extension Points

### Adding New Agents
1. Create agent class inheriting from `BaseAgent`
2. Define capabilities and skills
3. Register in `AGENT_REGISTRY`
4. Add skill mappings
5. Configure retry/fallback policies

### Custom Workflows
1. Define workflow in YAML/JSON
2. Register with orchestrator
3. Implement required agents
4. Configure error handling

---

## Conclusion

This agent system provides:
- **Autonomous operation** of all algorithm components
- **Scalable architecture** with multiple agent instances
- **Fault tolerance** with retry and fallback mechanisms
- **Observable operations** with comprehensive metrics
- **Extensible design** for adding new capabilities

The system enables patent-level innovations like demand-based redistribution and knowledge-based optimization through coordinated multi-agent workflows.