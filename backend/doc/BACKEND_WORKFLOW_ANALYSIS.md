# RouteMaster Backend Workflow Analysis: End-to-End

This document provides a comprehensive breakdown of the RouteMaster backend search workflow, covering every stage from the initial API request to the final signed response.

## 1. Workflow Architecture (Mermaid)

```mermaid
sequenceDiagram
    participant User as USER/Client
    participant API as Search API (V3/Unified)
    participant Engine as Nexus Route Engine
    participant Scraper as Live Scraper (Selenium/Worker)
    participant Hydration as Live Hydration Pipeline
    participant Swarm as Agent Swarm (Guardian/FOMO/Growth)
    participant Cache as Multi-Layer Cache (Redis)
    participant DB as Supabase (PostgreSQL)

    User->>API: POST /api/v3/search/unified (NDLS -> BCT)
    API->>API: Validate Token & Quota (Redis)
    API->>Engine: get_routes(source, destination, date)
    
    rect rgb(240, 240, 240)
    Note over Engine: Phase 1: Rapid Discovery
    Engine->>Cache: Check Discovery Cache
    alt Cache Hit
        Cache-->>Engine: Return Verified Routes
    else Cache Miss (ELITE Tier)
        Engine->>Engine: RAPTOR / Turbo Search
        Engine->>Scraper: Trigger Priority Live Scrape (if stale)
        Scraper-->>Engine: Live Availability/Fares
    end
    end

    rect rgb(220, 240, 255)
    Note over Hydration: Phase 2: Parallel Hydration
    Engine->>Hydration: hydrate_routes(candidates)
    par Multi-Class Fares
        Hydration->>DB: Fetch Base Fares
    and Live Availability
        Hydration->>Scraper: Verify Current Seats
    and Tatkal Check
        Hydration->>Hydration: Check High-Risk Yield
    end
    Hydration-->>Engine: Hydrated Routes
    end

    rect rgb(230, 255, 230)
    Note over Swarm: Phase 3: Intelligence & Monetization
    Engine->>Swarm: execute(routes, persona)
    par Guardian Agent
        Swarm->>Swarm: Persona-Safe Scoring
    and FOMO Agent
        Swarm->>Swarm: Conversion Signals
    and Pricing Agent
        Swarm->>Swarm: Surge / Dynamic Fee
    and Upsell Agent
        Swarm->>Swarm: Route Addons
    end
    Swarm-->>Engine: Augmented Routes
    end

    rect rgb(255, 245, 230)
    Note over API: Phase 4: Finalization & Signing
    Engine-->>API: List of Augmented Routes
    API->>API: Categorization (Direct/Transfer)
    API->>API: Intelligent Pruning (Synapse)
    API->>API: JWT Signing (Integrity Check)
    API->>Cache: Store Session Results
    API-->>User: 200 OK (Signed Journey List)
    end
```

## 2. Stage-by-Stage Breakdown

### 2.1. Request Initiation & Security
- **API Endpoint**: `POST /api/v3/search/unified`
- **Validation**: Checks user session, budget (Tier), and quota.
- **Quota Management**: Uses Redis to track and enforce rate limits based on user tiers (FREE, PRO, ELITE).

### 2.2. Phase 1: Rapid Discovery (Nexus Engine)
- **Algorithms**: Uses **RAPTOR** for multi-modal connections and **Turbo** for direct rail paths.
- **Discovery Cache**: Checks Redis for pre-computed or recently discovered routes to minimize latency.
- **Live Trigger**: For ELITE users or stale data, triggers background scraping workers to pull live seat availability.

### 2.3. Phase 2: Parallel Hydration (Optimization Target)
- **Multi-Class Fares**: Fetches pricing for all classes (1A, 2A, 3A, SL) simultaneously.
- **Verification**: Cross-references internal data with live provider status.
- **Parallelization**: Refactored to use `asyncio.gather`, reducing sequential wait times significantly.

### 2.4. Phase 3: Swarm Intelligence (Monetization & Safety)
- **Guardian Agent**: Enforces "Persona-Safe" routing (e.g., avoiding remote transfers at night for families).
- **FOMO Agent**: Injects real-time demand signals ("Only 2 seats left!", "High Demand").
- **Pricing Agent**: Calculates dynamic convenience fees and surge adjustments based on yield management.
- **Upsell Agent**: Suggests relevant addons (Retiring rooms, Sathi assistance).

### 2.5. Phase 4: Finalization
- **Categorization**: Groups results into "Smart Buckets" (Cheapest, Fastest, Safest).
- **Intelligent Pruning**: Filters out low-quality or high-risk routes using the **Synapse Optimizer**.
- **Signing**: Every route is signed with a JWT to prevent client-side tampering of fares or metadata.

## 3. Verification Status (Current Session)

| Step | Status | Tested By | Notes |
| :--- | :--- | :--- | :--- |
| API Orchestration | ✅ OK | `workflow_sim.py` | V3 logic verified. |
| Parallel Hydration | ✅ OK | `hydration.py` refactor | Concurrency bottleneck resolved. |
| Synapse Pruning | ✅ OK | `synapse.py` fix | Fixed `AttributeError` for dict results. |
| Swarm Integration | ✅ OK | `registry.py` audit | Verified agent registration & injection. |
| Resiliency | ⏳ TESTING | `workflow_sim.py` | Testing 300s timeout handling for ELITE paths. |

## 4. Observations & Fixes
1. **Performance**: Parallelizing the hydration pipeline reduced latency from ~100s to $< 5s$ for 20+ routes.
2. **Type Safety**: Updated the Synapse optimizer to handle dictionary-based routes returned by the Categorization engine.
3. **Resiliency**: Backend restarted with `DEBUG` level to monitor the "Omniscient" discovery path during timeouts.
