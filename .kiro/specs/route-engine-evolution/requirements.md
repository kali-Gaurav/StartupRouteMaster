# Route Engine Evolution - Requirements

## Overview
Next-generation route generation engine with AI-powered intelligence, progressive delivery, and safety integration.

## Tier 1 Features (Build Now)

### 1. SSE Progressive Route Delivery
**Owner:** SIGMA/KYLO | **Effort:** 1 day | **Impact:** ⭐⭐⭐⭐⭐

**Requirements:**
- Implement Server-Sent Events (SSE) streaming for route results
- First route delivered in < 500ms (direct trains)
- Transfer routes stream progressively as found
- Maintain backward compatibility with existing REST API
- Connection resilience with automatic reconnection

**Technical Specs:**
- Endpoint: `GET /api/v1/routes/search/stream`
- Event types: `route_found`, `search_complete`, `error`
- Heartbeat every 30 seconds to keep connection alive
- Fallback to REST if SSE not supported

### 2. Query Plan Optimizer (QPO)
**Owner:** SIGMA | **Effort:** 1 day | **Impact:** ⭐⭐⭐⭐

**Requirements:**
- Analyze query before routing execution
- Select optimal search depth (direct vs 1-transfer vs 2-transfer)
- Route to appropriate DB replica (read vs primary)
- Adjust hub list priority based on historical traffic
- Save 200-400ms average query time

**Technical Specs:**
- Input: QueryContext with src, dst, date, time, preferences
- Output: QueryPlan with search_strategy, depth, hub_priority
- Integration: Called before TurboRouter execution

### 3. Transfer Intelligence Score (TIS)
**Owner:** NOVA | **Effort:** 2 days | **Impact:** ⭐⭐⭐⭐⭐

**Requirements:**
- Calculate reliability score for each transfer point
- Historical on-time percentage for connecting trains
- Risk level classification: LOW (< 80%), MEDIUM (60-80%), HIGH (< 60%)
- UI integration with visual indicators
- Feed into route ranking algorithm

**Technical Specs:**
- Score range: 0-100
- Factors: historical on-time %, connection success rate, station buffer time
- Data source: Historical booking and travel data

### 4. Corridor Safety Bus (SOS ↔ Router)
**Owner:** SECURE/NEXUS | **Effort:** 1 day | **Impact:** ⭐⭐⭐⭐

**Requirements:**
- Real-time SOS event integration with routing
- Automatic route deprioritization in affected corridors
- Safety penalty applied to affected routes
- Kafka-based event streaming
- User auto-rerouting away from danger zones

**Technical Specs:**
- Kafka topic: `corridor.safety`
- Safety penalty: 0.0-1.0 multiplier on route score
- Cache invalidation on safety events

## Tier 2 Features (Next Quarter)

### 5. Contextual Availability Transformer (CAT)
- Transformer model for availability prediction
- Event calendar integration (festivals, IPL, exams)
- Weather-adjusted confidence scores
- 30-day availability probability curves

### 6. Journey DNA Pre-computation
- User travel pattern profiling
- Proactive route caching for frequent routes
- 50ms route display for predicted journeys
- India-specific behavior models

### 7. Data Source Arbitrage Engine (DSAE)
- Trust score per data source per station/train
- Adaptive API selection based on freshness/cost
- Staleness-triggered refresh mechanism
- Cost optimization within freshness constraints

## Tier 3 Features (Strategic Moonshots)

### 8. Event-Sourced Live Rail Graph (ELRG)
- Kafka-based real-time train position events
- GraphDB (Neo4j/DGraph) for live topology
- Dynamic routing based on actual positions
- 6-month initiative

### 9. RL Route Optimizer
- Shadow-mode RL agent observing queries
- Learn from user choices (booked vs rejected)
- Gradual scoring function adaptation
- Compounding intelligence over time

### 10. GTFS++ Schema
- Proprietary extended GTFS schema
- Coach-level occupancy data
- Platform assignment history
- Vendor reliability scores

## Integration Architecture

```
Query Request
    ↓
QPO (Query Plan Optimizer) - 50ms
    ↓
TurboRouter / RAPTOR - 500ms
    ↓
CAT + TIS Scoring - 100ms
    ↓
Frontier + Safety Filter - 50ms
    ↓
SSE Stream - 0ms perceived wait
    ↓
Client (Progressive Delivery)
```

## Success Metrics

| Metric | Target | Current |
|--------|--------|---------|
| First route delivery | < 500ms | ~1200ms |
| Average query time | < 700ms | ~1500ms |
| Transfer reliability score | 80%+ accuracy | N/A |
| Safety route flagging | 100% coverage | 0% |
| User satisfaction | > 4.5/5 | Unknown |

## Dependencies

- Kafka cluster for event streaming
- Redis Cluster for corridor-based caching
- PostgreSQL read replicas for query distribution
- ML infrastructure for CAT model