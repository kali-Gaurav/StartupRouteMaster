# Database Architect Deep-Dive Review Report
**Reviewer:** VAULT (Database Architect)
**Department:** Database & Services Layer
**Date:** 2026-05-22
**Scope:** Core Models, Infrastructure, Alembic Migrations, and Core Services (Booking, Inventory, User).

## Executive Summary
A comprehensive deep-dive into the RouteMaster database layer reveals critical architectural flaws in service lifecycles, connection management, and data integrity. While the core models are extensive and feature-rich, the execution strategy surrounding transaction boundaries and session sharing is structurally unsound for an asynchronous FastAPI application. 

Specifically, global singleton service instances are inappropriately holding onto transient request-scoped `AsyncSession` objects, and premature commits inside sub-routines cause permanent data leaks (e.g., seat inventory deductions) upon downstream failures. Additionally, a Supabase async connection blocker was identified where the SSL context is stripped but not replaced, guaranteeing connection rejections in production. Urgent remediation is required before scaling.

## Insights

### Category 1: Transaction Management & ACID Compliance

#### Insight #1: Unsafe Singleton Injection for Session-Bound Services
- **Severity:** 🔴 Critical
- **Type:** Architecture / Bug
- **File(s):** `backend/services/booking_service.py`, `backend/services/inventory_service.py`, `backend/services/user_service.py`
- **Finding:** Services that depend on SQLAlchemy database sessions are defined as global singletons (e.g., `inventory_service = None`). `booking_service.py` attempts to import `inventory_service` directly at module load, meaning it evaluates to `None`. Any call to `await inventory_service.allocate_seats(...)` will immediately raise an `AttributeError`. Even if `get_inventory_service(db)` were called to initialize it, it would permanently bind the singleton to the *first request's* DB session. When that session closes, all subsequent web requests will fail with "Session Closed" or detached instance errors.
- **Recommendation:** Remove global service singletons. Use FastAPI's dependency injection (`Depends()`) to yield service instances that wrap the request-scoped `db` session on every request.
- **Impact:** System-wide fatal crashes (`NoneType` exceptions) and cross-request session leakage causing 500 Internal Server Errors.

#### Insight #2: Premature Commits Leading to Seat Inventory Leaks
- **Severity:** 🔴 Critical
- **Type:** Bug / Business Risk
- **File(s):** `backend/services/booking_service.py`, `backend/services/inventory_service.py`
- **Finding:** In `create_booking`, `self.db.commit()` is aggressively called inside `_create_booking_record`, and again inside `inventory_service.allocate_seats`. If the booking workflow fails later (e.g., during `pricing_service.calculate_fare` or fraud detection), the transaction is already committed. The seats are permanently deducted from `available_seats` without any rollback mechanism.
- **Recommendation:** Shift transaction boundary management to the top-level controller/service method. Use `await self.db.flush()` within intermediate helper methods. Execute a single `await self.db.commit()` at the end of the successful workflow.
- **Impact:** Massive phantom bookings, revenue loss due to unbookable empty seats, and corrupted inventory state.

### Category 2: Schema Design & Normalization

#### Insight #3: Severe Model Attribute Mismatches in Booking
- **Severity:** 🔴 Critical
- **Type:** Bug
- **File(s):** `backend/services/booking_service.py`, `backend/database/models/core.py`
- **Finding:** `BookingService._create_booking_record` instantiates the `Booking` model with kwargs: `journey_id`, `class_type`, `from_station_code`, `to_station_code`, and `idempotency_key`. The `Booking` model in `core.py` **does not have these columns**. Furthermore, `_check_idempotency` queries `Booking.idempotency_key`, which does not exist (it exists on `BookingIdempotency`).
- **Recommendation:** Add the missing columns to the `Booking` model in `core.py` to match the service layer's expectations, or update the service to insert related data into the correct tables (e.g., querying the `BookingIdempotency` table).
- **Impact:** Immediate `ArgumentError` and `AttributeError` upon any attempt to create a booking.

#### Insight #4: Incorrect User Model Column References
- **Severity:** 🔴 Critical
- **Type:** Bug
- **File(s):** `backend/services/user_service.py`, `backend/database/models/core.py`
- **Finding:** `UserService` queries `User.phone`, instantiates `User(name=...)`, and returns `user.wallet_balance`. The `User` model defines these as `phone_number`, `full_name`, and `credit_balance` respectively.
- **Recommendation:** Map the `UserService` operations to the correct SQLAlchemy attributes: `phone_number`, `full_name`, and `credit_balance`.
- **Impact:** Fatal errors on user login, profile fetching, and account creation.

### Category 3: Supabase Integration Correctness

#### Insight #5: Asyncpg Supabase SSL Connection Rejection
- **Severity:** 🔴 Critical
- **Type:** Security / Architecture
- **File(s):** `backend/database/infrastructure/config.py`, `backend/database/infrastructure/session.py`
- **Finding:** When generating the async PostgreSQL URL, `Config.GET_SQLALCHEMY_URL` explicitly strips the `?sslmode=require` query parameter (because the `asyncpg` driver does not support it in the URI). However, `session.py` never injects a native Python `ssl.create_default_context()` into `connect_args`. Supabase enforces strict SSL for remote connections; stripping it causes the connection handshake to fail instantly.
- **Recommendation:** In `session.py`, when `asyncpg` is the dialect, import `ssl`, create an SSL context, and inject it: `connect_args={"ssl": ssl.create_default_context()}`.
- **Impact:** The backend will completely fail to connect to the Supabase Postgres instance in asynchronous mode.

### Category 4: Index Strategy & Query Optimization

#### Insight #6: Missing Await on AsyncSession Execution
- **Severity:** 🔴 Critical
- **Type:** Bug
- **File(s):** `backend/services/inventory_service.py`
- **Finding:** Throughout `InventoryService` (e.g., `get_availability`, `allocate_seats`), the code executes queries synchronously: `inventory = self.db.execute(select(...).with_for_update()).scalar_one_or_none()`. Since `self.db` receives an `AsyncSession`, `self.db.execute` returns a coroutine, which lacks the `.scalar_one_or_none()` method.
- **Recommendation:** Prepend `await` to all `self.db.execute(...)` calls in async service methods.
- **Impact:** Routine runtime crashes for all inventory operations.

### Category 5: Redis Caching Strategy

#### Insight #7: Blocking Synchronous Redis I/O in Async Loop
- **Severity:** 🟠 High
- **Type:** Performance / Bug
- **File(s):** `backend/services/cache/manager.py` (CacheService)
- **Finding:** `CacheService` is initialized with the synchronous `redis.Redis` client. The `incr()` and `expire()` methods are defined as `async def` but internally call blocking synchronous redis methods. This blocks the main FastAPI asyncio event loop, severely degrading concurrent request handling.
- **Recommendation:** Migrate `CacheService` to use `redis.asyncio.Redis` (similar to how `MultiLayerCache` is implemented), or offload sync calls to a `ThreadPoolExecutor`.
- **Impact:** Severe throughput degradation and latency spikes under load.

### Category 6: Data Integrity Constraints

#### Insight #8: Missing Database-Level Constraints for Seat Limits
- **Severity:** 🟡 Medium
- **Type:** Data Quality
- **File(s):** `backend/database/models/core.py`
- **Finding:** The `available_seats` column in `SeatInventory` is a plain `Integer`. While application logic attempts to prevent negative seats, a race condition or manual intervention could drive the count below zero.
- **Recommendation:** Implement a CheckConstraint on the `SeatInventory` table: `CheckConstraint('available_seats >= 0')`.
- **Impact:** Potential for negative seat allocations leading to passenger overbooking disputes.

#### Insight #9: Static Date Mismatch in Type Hints vs Database
- **Severity:** 🟢 Low
- **Type:** Best Practice
- **File(s):** `backend/services/booking_service.py`, `backend/services/inventory_service.py`
- **Finding:** `InventoryService.allocate_seats` types `travel_date` as `str`. However, `BookingService` passes `booking.travel_date`, which is a `datetime.date` object. SQLAlchemy handles this gracefully most of the time, but the type hinting mismatch causes static analysis confusion.
- **Recommendation:** Standardize travel dates across the service layer to use `datetime.date` consistently.
- **Impact:** Minor maintainability issue; possible edge-case serialization bugs.

## Summary Statistics
| Severity | Count |
|----------|-------|
| 🔴 Critical | 6 |
| 🟠 High | 1 |
| 🟡 Medium | 1 |
| 🟢 Low | 1 |
| 🔵 Info | 0 |
| **Total** | **9** |

## Top 10 Priority Actions
1. **Remove Global Service Singletons:** Refactor `booking_service.py`, `inventory_service.py`, and `user_service.py` to use FastAPI dependency injection for `AsyncSession`.
2. **Fix Booking Model Schema:** Add the missing columns (`journey_id`, `class_type`, `from_station_code`, etc.) to the `Booking` SQLAlchemy model to match the service layer.
3. **Correct User Model References:** Replace `.phone`, `.name`, and `.wallet_balance` in `UserService` with `.phone_number`, `.full_name`, and `.credit_balance`.
4. **Implement Transaction Boundaries:** Remove internal `commit()` calls in `BookingService` and `InventoryService` sub-routines. Use `flush()` and execute a single `commit()` at the end of the workflow.
5. **Add Asyncpg SSL Context:** Update `session.py` to supply an explicit SSL context to asyncpg connections when targeting Supabase.
6. **Await AsyncSession Queries:** Fix missing `await` keywords on all `self.db.execute(...)` calls inside `InventoryService`.
7. **Fix Redis Client Type:** Convert `CacheService` to utilize `redis.asyncio` rather than the blocking `redis` client.
8. **Add Check Constraints:** Apply a check constraint on `SeatInventory.available_seats` to enforce `> 0`.
9. **Synchronize Date Types:** Ensure `travel_date` variables use standard `datetime.date` across all type hints and DB interactions.
10. **Validate Idempotency Logic:** Refactor idempotency checks to query `BookingIdempotency` properly instead of an invalid attribute on the `Booking` model.
