# RouteMaster V2: Backend Audit & Upgrade Roadmap

## 1. Executive Summary
This document provides a line-by-line audit of the backend codebase, identifying gaps in implementation, data integrity issues, and required upgrades to achieve Phase 8 (Resilient Production) status.

**Primary Goal**: Ensure zero-redundancy, 100% database consistency (`transit_graph.db`), and verified multi-modal search logic.

---

## 2. Core Engine Audit (`backend/core/`)

| File | Status | Missing Gaps / Required Upgrades | Phase |
| :--- | :--- | :--- | :--- |
| `route_engine/raptor.py` | ACTIVE | Implement "Walking" transfer logic between hubs (RT-23); Add Pareto-optimization for 'Comfort' vs 'Price'. | Phase 1 |
| `route_engine/engine.py` | ACTIVE | Integrate `RealTimeMutationEngine` (RT-45) for live graph updates; Implement `ChaosValidationManager`. | Phase 5 |
| `route_engine/builder.py` | VERIFIED | Ensure all lookups use `transit_graph.db`. Currently has hardcoded paths in some helper methods. | Phase 3 |
| `data_provider.py` | ACTIVE | Complete RapidAPI fallback for Taxi prices (RT-12); Add caching for IRCTC seat lookups. | Phase 2 |

---

## 3. API Layer Audit (`backend/api/`)

| File | Status | Missing Gaps / Required Upgrades | Phase |
| :--- | :--- | :--- | :--- |
| `integrated_search.py` | ACTIVE | Add standard request validation decorators; Implement rate-limiting for search endpoints. | Phase 1 |
| `realtime.py` | SCAFFOLD | Connect to WebSocket stream for live train tracking; Implement `EventProcessor`. | Phase 5 |
| `bookings.py` | PARTIAL | Add transactional locking for seat allocation in `transit_graph.db`. | Phase 4 |
| `routemaster_integration.py`| ACTIVE | Refine prompt engineering for agent response speed. | Phase 7 |

---

## 4. Service Layer Audit (`backend/services/`)

| File | Status | Missing Gaps / Required Upgrades | Phase |
| :--- | :--- | :--- | :--- |
| `delay_predictor.py` | SCAFFOLD | Replace synthetic training data with historical IRCTC data; Implement `WeatherService` integration. | Phase 6 |
| `route_ranking_model.py`| SCAFFOLD | Implement User Preference Vector (UPV) storage in `transit_graph.db`. | Phase 6 |
| `verification_engine.py`| ACTIVE | Add PNR status scraping fallback; Verify fare calculation for 'Tatkal' bookings. | Phase 2 |

---

## 5. Database Schema Status

| Database | Tables | Health | Action |
| :--- | :--- | :--- | :--- |
| `railway_data.db` | 15 (GTFS) | EXCELLENT | Master reference. DO NOT MODIFY. |
| `transit_graph.db` | 74 (Live) | GOOD | Unified User/Booking/ML store. Needs Cleanup of 'temp_' tables. |

---
