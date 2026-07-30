# DB-004: Database Audit Logging

## Problem / Goal

Currently, the system has no comprehensive audit trail of data mutations. When data changes (INSERT/UPDATE/DELETE), there's no record of who made the change, when it happened, or what the previous values were. This creates compliance risks (GDPR/data privacy regulations), makes debugging harder, and prevents forensic analysis of data changes. Implement complete audit logging for all database mutations with queryable audit trails and configurable retention policies.

## Scope

**Files Expected to Change:**
- `backend/audit/audit_logger.py` — new module for audit logging logic
- `backend/audit/__init__.py` — module initialization and exports
- `backend/database/models/audit.py` — SQLAlchemy audit log table models
- `database/migrations/audit_tables.sql` — database schema for audit tables
- `backend/middleware/audit_middleware.py` — middleware to capture mutation context (user, timestamp, IP)
- `backend/tests/test_audit_logging.py` — comprehensive test suite
- `backend/config/audit.py` — audit configuration (retention, sampling, etc.)

**Non-Goals:**
- Real-time audit streaming to external systems (separate feature)
- Audit log encryption (covered by DB-005: Data Encryption at Rest)
- Audit log analytics dashboard (separate feature)
- Fine-grained field-level change tracking (v2 feature)

## Exit Criteria

1. ✅ **100% of data mutations logged** — every INSERT, UPDATE, DELETE on core tables is captured in audit log
   - Verification: Run mutation test suite, verify audit table has entry for each mutation
   - Core tables: routes, users, bookings, trips (identified from schema)

2. ✅ **Queryable audit trail** — audit logs can be queried by user, table, timestamp, operation type
   - Verification: Test queries: find all changes by user X in date range Y; find all DELETE operations
   - Query performance: < 100ms for queries on 1M records

3. ✅ **User context captured** — each audit log entry includes user_id, username, timestamp, IP address, operation
   - Verification: Audit log entries contain user_id, timestamp, operation_type, original_values, new_values

4. ✅ **Before/after values stored** — UPDATE operations store both old and new values for changed columns
   - Verification: Sample UPDATE audit entry shows before/after JSON
   - Storage format: JSON for flexibility (supports all data types)

5. ✅ **Retention policy configurable** — audit logs can be aged out based on retention policy (30d default)
   - Verification: Migration includes retention policy, can be updated without code changes
   - Auto-cleanup: Optional scheduled job to archive/delete old logs

6. ✅ **All tests pass** — unit tests for audit logger, integration tests with real mutations
   - Verification: pytest backend/tests/test_audit_logging.py — all passing
   - Coverage: Core mutations (create, update, delete), edge cases (concurrent updates, transaction rollback)

7. ✅ **Code follows project conventions** — uses existing patterns, proper error handling, type hints
   - Verification: Code review against project standards
   - Database: Uses SQLAlchemy ORM patterns
   - Middleware: Follows existing middleware pattern

## Implementation Approach

### Architecture

1. **Audit Logger** (backend/audit/audit_logger.py)
   - Singleton that intercepts SQLAlchemy mutations
   - Captures table name, operation type (INSERT/UPDATE/DELETE), before/after values
   - Stores context: user_id, timestamp, IP address, session info

2. **Audit Middleware** (backend/middleware/audit_middleware.py)
   - Captures request context (user_id, IP, user-agent)
   - Stores in request-local storage for audit logger to access
   - Works with FastAPI/async request lifecycle

3. **Audit Models** (backend/database/models/audit.py)
   - AuditLog table with columns: id, table_name, operation_type, record_id, user_id, timestamp, before_values, after_values, ip_address
   - Indexes on: (table_name, timestamp), (user_id, timestamp), operation_type
   - Retention policy column (auto-delete after N days)

4. **Database Schema** (database/migrations/audit_tables.sql)
   - Create audit_log table with proper indexes and constraints
   - Ensure immutability: audit log entries are INSERT-only (no UPDATE/DELETE of audit rows)

### Technology Choices

- **Storage**: PostgreSQL audit_log table (same database as operational data)
- **Capture Method**: SQLAlchemy event listeners (`before_insert`, `before_update`, `before_delete`)
- **Data Format**: JSON for before/after values (handles all types, human-readable)
- **Middleware**: FastAPI dependency for capturing user context

### Known Constraints

- **Circular dependency risk**: Audit logger must not trigger infinite loops if audit table changes are audited (solution: exclude audit tables from audit logging)
- **Performance**: Audit logging adds ~5-10% overhead to write operations (acceptable, can be optimized later)
- **Async compatibility**: Must work with async SQLAlchemy operations

## Verification Plan

**Type**: Test-based (backend feature)

**Steps**:
1. Unit tests: Audit logger correctly formats mutations
2. Integration tests: Create/update/delete operations trigger audit logging
3. Query tests: Audit logs can be filtered by user, table, timestamp
4. Edge cases: Concurrent updates, transaction rollback, NULL values, large objects
5. Performance: Query latency < 100ms on 1M records
6. Code review: Against project conventions

**Success**: All 16+ tests pass, audit log populated correctly for sample mutations, queries return expected results

## Related Features

- **DB-003** (Read Replicas): Audit logging works independently
- **DB-005** (Data Encryption): Audit log values encrypted separately if needed
- **DB-007** (Monitoring): Can monitor audit log size growth

---

**Backlog Context**: P1 priority, Medium effort, Core compliance feature
