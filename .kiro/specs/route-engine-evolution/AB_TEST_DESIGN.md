# Route Engine Evolution - A/B Test Design

**Feature:** Route Engine Intelligence Features  
**Owner:** VERA (Data Analyst)  
**Status:** 🔄 DESIGN COMPLETE  
**Date:** 2026-05-08

---

## Overview

This document defines the A/B testing strategy for evaluating the Route Engine Evolution features, including SSE Progressive Delivery, Transfer Intelligence Score (TIS), and Corridor Safety Bus.

---

## Test Hypothesis

### Primary Hypothesis

> **Implementing the Tiered Intelligence Pipeline (QPO → RAPTOR → TIS → Safety → SSE) will increase booking conversion rate by 5-10% compared to the baseline route engine.**

### Secondary Hypotheses

1. **SSE Progressive Delivery**: Users will perceive the search as faster and have lower bounce rates
2. **Transfer Intelligence Score**: Users will book routes with better connections, reducing missed transfers
3. **Corridor Safety Bus**: Users will have higher trust in the platform during adverse conditions

---

## Test Design

### Control Group (A)

- **Treatment:** Existing route engine (baseline)
- **Features:** Standard route search without intelligence features
- **Expected Behavior:** Current conversion rate (~2.5%)

### Treatment Group (B)

- **Treatment:** New Route Engine Evolution
- **Features:**
  - SSE progressive route delivery
  - Transfer Intelligence Score indicators
  - Corridor Safety Bus integration
  - Query Plan Optimizer
- **Expected Behavior:** Improved conversion rate (2.75-2.75%)

### Test Duration

| Phase | Duration | Purpose |
|-------|----------|---------|
| Ramp-up | 1 week | 10% → 50% traffic |
| Full test | 2 weeks | 50% traffic to both groups |
| Cooldown | 1 week | Monitor for anomalies |

**Total Duration:** 4 weeks

### Sample Size

Using calculator with:
- Baseline conversion rate: 2.5%
- Minimum detectable effect: 5% relative (0.125% absolute)
- Statistical power: 80%
- Significance level: 95%

```
Required sample size: ~500,000 searches per group
Expected duration: 2 weeks at 50,000 searches/day
```

---

## Metrics

### Primary Metrics

| Metric | Definition | Target |
|--------|------------|--------|
| **Booking Conversion Rate** | Bookings / Searches | +5-10% |
| **Revenue per Search** | Total Revenue / Searches | +5-8% |

### Secondary Metrics

| Metric | Definition | Target |
|--------|------------|--------|
| **Search Completion Rate** | Completed searches / Total searches | +3% |
| **Route Selection Time** | Time from results to selection | -10% |
| **Booking Abandonment Rate** | Abandoned bookings / Initiated bookings | -5% |
| **NPS (Net Promoter Score)** | Post-booking survey | +5 points |

### Guardrail Metrics

| Metric | Definition | Threshold |
|--------|------------|-----------|
| **Error Rate** | Failed searches / Total searches | < 1% |
| **P95 Latency** | 95th percentile response time | < 1.5s |
| **Page Load Time** | Time to first meaningful content | < 2s |

### Feature-Specific Metrics

#### SSE Progressive Delivery

| Metric | Definition | Target |
|--------|------------|--------|
| **Time to First Route** | Time to first SSE event | < 500ms |
| **SSE Connection Rate** | Successful SSE connections / Attempts | > 95% |
| **Reconnection Rate** | Reconnections / Total connections | < 5% |

#### Transfer Intelligence Score

| Metric | Definition | Target |
|--------|------------|--------|
| **TIS Score Distribution** | % of routes by risk level | Balanced |
| **User Click-through** | Clicks on TIS indicators | > 30% |
| **Transfer Success Rate** | Successful transfers / Total transfers | +5% |

#### Corridor Safety Bus

| Metric | Definition | Target |
|--------|------------|--------|
| **Safety Event Detection** | Events detected / Actual events | > 90% |
| **Route Avoidance** | Routes avoided due to safety | 1-3% |
| **User Trust Score** | Post-search survey | +3 points |

---

## Implementation

### Feature Flags

```python
# backend/api/middleware/feature_flags.py

from enum import Enum
from dataclasses import dataclass
from typing import Dict, Any
import random

class FeatureFlag(Enum):
    SSE_STREAMING = "sse_streaming"
    TRANSFER_INTELLIGENCE = "transfer_intelligence"
    CORRIDOR_SAFETY = "corridor_safety"
    QUERY_OPTIMIZER = "query_optimizer"

@dataclass
class FeatureConfig:
    enabled: bool
    rollout_percentage: int  # 0-100

# Feature flag configuration
FEATURE_FLAGS: Dict[FeatureFlag, FeatureConfig] = {
    FeatureFlag.SSE_STREAMING: FeatureConfig(enabled=True, rollout_percentage=50),
    FeatureFlag.TRANSFER_INTELLIGENCE: FeatureConfig(enabled=True, rollout_percentage=50),
    FeatureFlag.CORRIDOR_SAFETY: FeatureConfig(enabled=True, rollout_percentage=50),
    FeatureFlag.QUERY_OPTIMIZER: FeatureConfig(enabled=True, rollout_percentage=50),
}

def is_feature_enabled(flag: FeatureFlag, user_id: str = None) -> bool:
    """Check if a feature is enabled for a user"""
    config = FEATURE_FLAGS.get(flag)
    if not config or not config.enabled:
        return False
    
    # Check rollout percentage
    if user_id:
        # Consistent assignment based on user ID
        user_bucket = hash(user_id) % 100
        return user_bucket < config.rollout_percentage
    
    return random.random() * 100 < config.rollout_percentage

def get_user_variant(user_id: str) -> str:
    """Assign user to A/B test variant"""
    user_bucket = hash(user_id) % 100
    return "B" if user_bucket < 50 else "A"
```

### Event Tracking

```python
# backend/api/middleware/analytics.py

from datetime import datetime
from typing import Dict, Any
import json

class AnalyticsTracker:
    """Track A/B test events"""
    
    def __init__(self):
        self.events = []
    
    async def track_search(
        self,
        user_id: str,
        variant: str,
        query: Dict[str, Any],
        results_count: int,
        latency_ms: int
    ):
        """Track search event"""
        event = {
            "event_type": "search",
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "variant": variant,
            "query": query,
            "results_count": results_count,
            "latency_ms": latency_ms,
            "features": {
                "sse_enabled": is_feature_enabled(FeatureFlag.SSE_STREAMING, user_id),
                "tis_enabled": is_feature_enabled(FeatureFlag.TRANSFER_INTELLIGENCE, user_id),
                "safety_enabled": is_feature_enabled(FeatureFlag.CORRIDOR_SAFETY, user_id),
            }
        }
        await self._send_event(event)
    
    async def track_route_selection(
        self,
        user_id: str,
        route_id: str,
        tis_score: float = None,
        safety_score: float = None
    ):
        """Track route selection event"""
        event = {
            "event_type": "route_selection",
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "route_id": route_id,
            "tis_score": tis_score,
            "safety_score": safety_score
        }
        await self._send_event(event)
    
    async def track_booking(
        self,
        user_id: str,
        booking_id: str,
        route_id: str,
        revenue: float
    ):
        """Track booking event"""
        event = {
            "event_type": "booking",
            "timestamp": datetime.utcnow().isoformat(),
            "user_id": user_id,
            "booking_id": booking_id,
            "route_id": route_id,
            "revenue": revenue
        }
        await self._send_event(event)
    
    async def _send_event(self, event: Dict[str, Any]):
        """Send event to analytics pipeline"""
        # In production, send to Kafka/Redshift
        self.events.append(event)
        print(f"Event tracked: {event['event_type']}")
```

### Dashboard Queries

```sql
-- Query: Conversion rate by variant
SELECT 
    variant,
    COUNT(DISTINCT CASE WHEN event_type = 'search' THEN user_id END) AS searches,
    COUNT(DISTINCT CASE WHEN event_type = 'booking' THEN user_id END) AS bookings,
    COUNT(DISTINCT CASE WHEN event_type = 'booking' THEN user_id END)::FLOAT / 
        NULLIF(COUNT(DISTINCT CASE WHEN event_type = 'search' THEN user_id END), 0) AS conversion_rate
FROM analytics_events
WHERE timestamp >= NOW() - INTERVAL '2 weeks'
GROUP BY variant;

-- Query: Latency by variant
SELECT 
    variant,
    AVG(latency_ms) AS avg_latency,
    PERCENTILE_CONT(0.95) WITHIN GROUP (ORDER BY latency_ms) AS p95_latency
FROM analytics_events
WHERE event_type = 'search'
GROUP BY variant;

-- Query: TIS indicator engagement
SELECT 
    variant,
    COUNT(*) AS total_selections,
    COUNT(CASE WHEN tis_score IS NOT NULL THEN 1 END) AS tis_engaged,
    COUNT(CASE WHEN tis_score IS NOT NULL THEN 1 END)::FLOAT / COUNT(*) AS engagement_rate
FROM analytics_events
WHERE event_type = 'route_selection'
GROUP BY variant;
```

---

## Statistical Analysis

### Significance Testing

```python
# analysis/ab_test_analysis.py

from scipy import stats
import numpy as np

class ABTestAnalyzer:
    """Analyze A/B test results"""
    
    def __init__(self, group_a_data, group_b_data):
        self.group_a = group_a_data
        self.group_b = group_b_data
    
    def test_conversion_rate(self):
        """Test conversion rate significance"""
        # Two-proportion z-test
        n_a = len(self.group_a)
        n_b = len(self.group_b)
        conversions_a = sum(self.group_a)
        conversions_b = sum(self.group_b)
        
        p_a = conversions_a / n_a
        p_b = conversions_b / n_b
        p_pooled = (conversions_a + conversions_b) / (n_a + n_b)
        
        se = np.sqrt(p_pooled * (1 - p_pooled) * (1/n_a + 1/n_b))
        z_score = (p_b - p_a) / se
        p_value = 2 * (1 - stats.norm.cdf(abs(z_score)))
        
        return {
            "z_score": z_score,
            "p_value": p_value,
            "significant": p_value < 0.05,
            "lift": (p_b - p_a) / p_a,
            "confidence_interval": self._confidence_interval(p_a, p_b, n_a, n_b)
        }
    
    def _confidence_interval(self, p_a, p_b, n_a, n_b, confidence=0.95):
        """Calculate confidence interval for difference"""
        se = np.sqrt(p_a * (1-p_a)/n_a + p_b * (1-p_b)/n_b)
        z = stats.norm.ppf((1 + confidence) / 2)
        diff = p_b - p_a
        return (diff - z * se, diff + z * se)
    
    def test_latency(self):
        """Test latency difference"""
        t_stat, p_value = stats.ttest_ind(
            self.group_a['latency'],
            self.group_b['latency']
        )
        
        return {
            "t_statistic": t_stat,
            "p_value": p_value,
            "significant": p_value < 0.05,
            "group_a_mean": np.mean(self.group_a['latency']),
            "group_b_mean": np.mean(self.group_b['latency'])
        }
```

---

## Timeline

| Week | Activity | Deliverable |
|------|----------|-------------|
| 1 | Implement feature flags and tracking | Feature flag system |
| 1 | Set up analytics pipeline | Dashboard |
| 2 | Ramp up to 50% traffic | Traffic report |
| 3 | Complete full test | Data collection |
| 4 | Analyze results | Analysis report |
| 4 | Decision: Rollout/Iterate | Go/No-go decision |

---

## Success Criteria

| Metric | Minimum Success | Target Success |
|--------|-----------------|----------------|
| Conversion Rate Lift | +3% | +7% |
| Statistical Significance | 90% confidence | 95% confidence |
| Error Rate | < 2% | < 1% |
| P95 Latency | < 2s | < 1.5s |

---

## Rollout Decision Matrix

| Result | Action |
|--------|--------|
| Significant positive lift | Full rollout (100%) |
| Positive but not significant | Continue test 1 week |
| No change | Evaluate cost-benefit |
| Negative lift | Rollback, investigate |

---

## Risk Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Insufficient sample size | Inconclusive results | Extend test duration |
| Seasonality effects | Biased results | Run for minimum 2 weeks |
| Technical issues | Invalid data | Monitoring and alerts |
| User segment differences | Uneven results | Segment analysis |

---

## Action Items

| ID | Action | Owner | Status |
|----|--------|-------|--------|
| AB-01 | Implement feature flags | SIGMA | 🔴 PENDING |
| AB-02 | Set up event tracking | SIGMA | 🔴 PENDING |
| AB-03 | Create analytics dashboard | VERA | 🔴 PENDING |
| AB-04 | Implement statistical analysis | VERA | 🔴 PENDING |
| AB-05 | Configure alerts | VERA | 🔴 PENDING |
| AB-06 | Document decision criteria | VERA | 🔴 PENDING |

---

**Document Version:** 1.0  
**Next Review:** 2026-05-15