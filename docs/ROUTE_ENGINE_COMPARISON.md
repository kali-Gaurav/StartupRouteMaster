# Route Engine Comparison

This document provides a detailed comparison of the three core route generation files identified in the `backend/core/` directory:
1.  `backend/core/route_engine.py`
2.  `backend/core/multi_modal_route_engine.py`
3.  `backend/core/advanced_route_engine.py`

Understanding their differences is crucial for selecting the most appropriate engine for specific routing requirements.

---

## 1. `backend/core/route_engine.py` (Simple RAPTOR)

This module implements a foundational RAPTOR (Round-Based Public Transit Routing Algorithm) primarily optimized for railway networks.

*   **Algorithms Used:** Implements the RAPTOR algorithm for finding multi-transfer routes.
*   **Modality Support:** Primarily designed for single-modal (train/railway) routing. Its data structures and segments are tailored for train journeys.
*   **Data Models:** Directly interacts with SQLAlchemy ORM models defined in `backend/database/models.py` (e.g., `Stop`, `Trip`, `StopTime`, `Route`, `Calendar`, `CalendarDate`, `Transfer`). It loads this data into a `TimeDependentGraph` for internal processing.
*   **Feature Set:**
    *   Basic multi-transfer route finding.
    *   Multi-objective scoring (time, cost, comfort, safety).
    *   Pre-computed route patterns and transfer graphs.
    *   Time-dependent graph with real-time delay injection capability (though the implementation details for "injection" are somewhat abstract).
    *   Integration with `backend/services/multi_layer_cache.py` for caching search results.
*   **Dependencies:**
    *   `sqlalchemy` (for ORM interactions)
    *   `datetime`, `collections`, `heapq` (standard Python libraries)
    *   `backend.database`
    *   `backend.database.models`
    *   `backend.database.config` (aliased as `Config`)
    *   `backend.services.multi_layer_cache`
*   **Maturity/Complexity:** Represents a solid, optimized, single-modal RAPTOR implementation. It's efficient for its core task but lacks broader multi-modal or advanced algorithmic features.

---

## 2. `backend/core/multi_modal_route_engine.py` (Multi-Modal RAPTOR)

This engine extends the RAPTOR concept to support multi-modal transit data and more complex journey types.

*   **Algorithms Used:** A multi-modal RAPTOR algorithm, capable of handling transfers between different transport modes.
*   **Modality Support:** Explicitly supports various transport modes like tram, subway, rail, and bus, making it suitable for urban transit systems or integrated journey planning.
*   **Data Models:** Directly interacts with SQLAlchemy ORM models from `backend/database/models.py` during its `load_graph_from_db` method. It then populates its own in-memory data structures (e.g., `stops_map`, `routes_map`, `trips_map`) for faster lookup during routing.
*   **Feature Set:**
    *   Comprehensive multi-modal journey finding.
    *   Supports connecting journeys, circular (round-trip) journeys, and multi-city booking.
    *   Detailed fare calculation, including mode-specific pricing, passenger type discounts, and concessions.
    *   Simulation of real-time delays and handling of disruptions (`Disruption` model).
    *   PNR-like reference generation for bookings.
    *   Integration with `backend.services.cache_service` and its own Redis client.
*   **Dependencies:**
    *   `sqlalchemy` (for ORM interactions)
    *   `redis` (for caching)
    *   `json`, `hashlib`, `hmac` (standard Python libraries)
    *   `backend.database`
    *   `backend.database.models`
    *   `backend.database.config` (aliased as `Config`)
    *   `backend.services.cache_service`
*   **Maturity/Complexity:** More feature-rich than the simple RAPTOR, especially for applications requiring complex journey planning, diverse transport modes, and commercial functionalities like fare calculation and booking references. It's designed for a broader scope of transit scenarios.

---

## 3. `backend/core/advanced_route_engine.py` (Advanced Route Engine)

This module represents a highly sophisticated, production-grade routing engine that combines multiple algorithms and a robust architectural design.

*   **Algorithms Used:**
    *   **RAPTOR (via `RaptorRouter`):** For fast point-to-point routing.
    *   **A* (via `AStarRouter`):** Employs geographic heuristics for efficient pathfinding, particularly useful when geographic distance provides strong guidance.
    *   **Yen's k-shortest paths (via `YensKShortestPaths`):** Finds multiple alternative (k-shortest) routes, offering users more choices based on various criteria.
*   **Modality Support:** Highly flexible and explicitly supports a wide range of transport modes through its `TransportMode` enum: `TRAIN`, `BUS`, `FLIGHT`, `METRO`, `AUTO`.
*   **Data Models:** Crucially, it defines its *own internal dataclasses* (`Stop`, `StopTime`, `Trip`, `Segment`, `Route`) for its graph representation. These are distinct from the SQLAlchemy models in `backend/database/models.py`. This separation of concerns allows for a more algorithm-specific and potentially more performant in-memory graph.
*   **Feature Set:**
    *   Combines the strengths of multiple routing algorithms.
    *   Intelligent transfer logic (`TransferValidator`) for validating connections between segments.
    *   Provides multiple alternative routes (k-shortest paths).
    *   Real-time graph updates (abstracted via an injected `network_service`).
    *   Intelligent caching mechanisms with Redis.
    *   Designed for extensibility and maintainability due to its clean architecture and reliance on a `network_service` abstraction for data access rather than direct ORM calls.
*   **Dependencies:**
    *   `sqlalchemy.orm.Session` (though primarily abstracted by `network_service`)
    *   `redis` (for caching)
    *   `numpy` (imported, but direct usage for the core routing logic is minimal in the provided code)
    *   `math` (for haversine distance calculations)
    *   Requires an injected `network_service` to retrieve stop, trip, and other network data, promoting loose coupling.
*   **Maturity/Complexity:** This is the most architecturally robust and algorithmically comprehensive engine. Its use of internal data models and a `network_service` abstraction makes it highly adaptable to different data sources and provides a clean interface for injecting data, promoting testability and modularity. It's best suited for complex, high-performance routing systems.

---

## Conclusion

| Feature / Engine                | `route_engine.py` (Simple RAPTOR) | `multi_modal_route_engine.py` (Multi-Modal RAPTOR) | `advanced_route_engine.py` (Advanced) |
| :------------------------------ | :-------------------------------- | :------------------------------------------------ | :------------------------------------ |
| **Primary Algorithm**           | RAPTOR                            | Multi-modal RAPTOR                                | RAPTOR, A*, Yen's k-shortest paths    |
| **Modality**                    | Single-modal (Railway)            | Multi-modal (Train, Bus, Tram, Subway)            | Full Multi-modal (Train, Bus, Flight, Metro, Auto) |
| **Data Models**                 | Uses `backend.database.models`    | Uses `backend.database.models` (to build in-memory maps) | Defines own internal dataclasses      |
| **Database Interaction**        | Direct SQLAlchemy ORM             | Direct SQLAlchemy ORM (initial load)              | Abstracted via `network_service`      |
| **Fare Calculation**            | Basic (`RouteSegment.fare`)       | Comprehensive (with concessions)                  | Not explicitly in engine, but segment cost is present |
| **Journey Types**               | Point-to-point                    | Connecting, Circular, Multi-city                  | Point-to-point, Alternatives (k-shortest) |
| **Real-time Updates**           | Yes (delay, cancel, occupancy)    | Yes (simulated delays/disruptions)                | Yes (abstracted via graph mutation)   |
| **Caching**                     | `multi_layer_cache`               | `cache_service`, direct Redis                     | Direct Redis                          |
| **Architectural Robustness**    | Good                              | Very Good                                         | Excellent (loosely coupled)           |

**Recommendation:**

For a system that aims for "perfectly generating routes and easily understanding," the **`backend/core/advanced_route_engine.py`** is the recommended choice. Its multi-algorithmic approach provides flexibility and comprehensive search capabilities, while its abstracted data access and internal data models contribute to a more robust, maintainable, and extensible architecture. While it requires a `network_service` implementation to feed it data, this design pattern is a significant advantage for complex systems.

The `multi_modal_route_engine.py` is also a strong contender if the primary focus is on complex multi-modal journey types (connecting, circular, multi-city) with comprehensive fare calculations, and a direct ORM interaction is acceptable.

The `route_engine.py` is best suited if only a basic, high-performance railway-specific RAPTOR is required without the advanced features or multi-modal complexities.

Ultimately, the "best" choice depends on the specific product requirements, scalability needs, and future extensibility goals. However, the `AdvancedRouteEngine` provides the most comprehensive and flexible foundation for a modern routing system.