# Architectural Analysis: SOS Module Type Safety

## Dependency Chain

```
backend/api/sos.py (MAIN FILE)
├── Imports from database/models.py
│   ├── SOSEvent (ORM model)
│   ├── SOSTelemetry (related model)
│   ├── User (FK reference)
│   └── Profile (for karma rewards)
├── Imports from services/emergency/alert_manager.py
│   └── EmergencyAlertManager.process_sos_alert()
├── Imports from database/session.py
│   ├── SessionLocal (sync ORM session)
│   └── Session (type hint)
├── Imports from services/multi_layer_cache.py
│   └── multi_layer_cache (Redis/cache abstraction)
├── Imports from database/config.py
│   └── Config.REDIS_URL
├── External: redis library
│   └── Sync client: redis.from_url()
└── External: pydantic, fastapi, sqlalchemy
```

## Data Flow Patterns

### Pattern 1: Event Creation Flow
```
SOSPayload (FastAPI request body)
  ↓ (parse via Pydantic)
new_event: Dict[str, Any]
  ↓ (async enrichment)
EmergencyAlertManager.process_sos_alert(new_event)
  ↓ (returns enriched Dict)
enriched_event: Dict[str, Any]
  ↓ (async persist to cache + DB)
_save_event_async(enriched_event, db)
  ├── Redis: cache.put(key, encrypted_event)
  └── Postgres: (async background task) SOSEvent.create()
  ↓ (response mapping)
_map_event_to_res(enriched_event)
  ↓
SOSEventResponse (FastAPI response)
```

### Pattern 2: Event Retrieval Flow
```
event_id: str (path param)
  ↓
_load_event_async(event_id, db)
  ├── Try: Redis cache.get(key)
  │   └── Success: decrypt + decompress
  └── Fallback: db.query(SOSEvent).filter(id=event_id)
  ↓ (returns Optional[Dict])
event: Optional[Dict[str, Any]]
  ↓ (guard check)
if event:
  ↓ (response mapping)
  _map_event_to_res(event)
  ↓
  SOSEventResponse
else:
  HTTPException 404
```

### Pattern 3: Database Synchronization
```
_save_event_async(event: Dict, db: Session)
  ├── Step 1: Encrypt via utils.encryption.encrypt_sos_event()
  ├── Step 2: Compress heavy fields (chat_history, call_logs)
  ├── Step 3: multi_layer_cache.put() (async)
  ├── Step 4: Redis index update (async)
  └── Step 5: Background DB persistence
      └── asyncio.create_task(_async_persist())
          ├── Query: db.query(SOSEvent).filter(id=event['id']).first()
          ├── Upsert logic:
          │   ├── Create new SOSEvent if not exists
          │   └── Update all fields from decrypted event
          └── Sync back to Redis
```

## Type Safety Issues by Pattern

### Issue Class A: ORM Descriptor Assignment
When assigning from `Dict` to ORM model attributes:

```python
# Problem:
sos_record.user_id = event.get("user_id")  # Any | None → needs Column[str]

# Why:
# 1. SOSEvent.user_id is defined as Column(String(36), ...)
# 2. SQLAlchemy uses descriptor protocol
# 3. Type stubs declare Column[T] as the attribute type
# 4. Runtime behavior accepts T value, but type system sees Column[T]

# Solution options:
# A) Type assertion: cast(str, event.get("user_id"))
# B) Default provision: event.get("user_id") or ""
# C) Type narrowing: if (val := ...) is not None: sos_record.user_id = val
# D) SQLAlchemy 2.0 style: use Mapped[] with mapped_column
```

### Issue Class B: Column Conditional Evaluation
When using Column objects in conditional statements:

```python
# Problem:
if sos_record.resolved_at:  # Column.__bool__ → NoReturn
    # AttributeError: Boolean coercion prohibited

# Why:
# SQLAlchemy specifically prevents truthiness evaluation to avoid ambiguity
# You might mean: "Is field NULL?" or "Is field truthy?" or "Is field in query?"

# Solution:
if sos_record.resolved_at is not None:
    # Now safe - explicit None check
```

### Issue Class C: Query Result Type Ambiguity
When extracting values from query results:

```python
# Problem:
for r in db.query(SOSEvent).all():
    await _load_event_async(r.id, db)  # r.id is Column[str], needs str

# Why:
# Type stubs represent query result attributes as Column[T]
# Runtime provides T value, but stubs are conservative

# Solutions:
# Option 1: Explicit str() call
ids = [str(r.id) for r in results]

# Option 2: Use .scalars()
ids = db.query(SOSEvent.id).scalars().all()

# Option 3: Type narrowing
from typing import cast
id_str = cast(str, r.id)
```

### Issue Class D: Async/Sync Redis Mismatch
When mixing Redis client types:

```python
# Problem:
import redis
sync_redis = redis.from_url(url)
raw_ids = sync_redis.smembers(key)  # Returns Set[bytes], not Awaitable

# But code treats as async:
ids = [i.decode() for i in raw_ids]  # ❌ Can't iterate Awaitable

# Why:
# Two different Redis libraries:
# - redis: synchronous client
# - redis.asyncio: async coroutines

# Solution:
# 1) Consistent use of sync redis
import redis
sync_redis = redis.from_url(url)
raw_ids = sync_redis.smembers(key)  # Sync call, returns Set immediately

# 2) Or consistent async
import redis.asyncio
async_redis = redis.asyncio.from_url(url)
raw_ids = await async_redis.smembers(key)  # Async call, returns Set after await
```

## ORM Model Typing Patterns

### Current Pattern (SQLAlchemy v1.x style)
```python
class SOSEvent(UserBase):
    __tablename__ = "sos_events"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    status = Column(String(20), default="ACTIVE")

# Issue:
# Pylance sees: SOSEvent.user_id has type Column[str] | None
# We write: sos_record.user_id = value_str
# Type error: str | None → Column[str]
```

### Recommended Pattern (SQLAlchemy v2.0 style)
```python
from sqlalchemy.orm import Mapped, mapped_column

class SOSEvent(UserBase):
    __tablename__ = "sos_events"
    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id: Mapped[Optional[str]] = mapped_column(String(36), ForeignKey("users.id"), nullable=True)
    status: Mapped[str] = mapped_column(String(20), default="ACTIVE")

# Benefit:
# Pylance sees: SOSEvent.user_id has type Optional[str]
# We write: sos_record.user_id = value_str  # Directly compatible
# No type errors!
```

**Migration Impact**: Updating models.py to use `Mapped[]` would resolve ~60% of type errors automatically, but requires careful refactoring of 50+ columns.

## Caching Architecture

```
Multi-Layer Cache System:
┌─────────────────────────────────────────────┐
│ L1 Cache (In-Memory, ~5sec TTL)             │
│ Extremely hot SOS event states              │
│ Cache miss → L2                             │
└──────────────┬──────────────────────────────┘
               │
┌──────────────▼──────────────────────────────┐
│ L2 Cache (Redis, 3-day TTL)                 │
│ Encrypted + compressed payloads             │
│ Cache miss → L3 (Postgres)                  │
└──────────────┬──────────────────────────────┘
               │
┌──────────────▼──────────────────────────────┐
│ L3 Store (PostgreSQL, permanent)            │
│ Raw decrypted data for audit/recovery       │
│ Retrieved on L1/L2 miss                     │
└──────────────────────────────────────────────┘
```

### Cache Operations
- **Put**: Async to L1 + L2, background sync to L3
- **Get**: Async from L2, with optional L1 inline cache
- **Index**: Redis set of active event IDs for quick enumeration
- **Registry**: PNR → Event ID mapping for fast lookups

### Type Safety in Caching
```python
async def _save_event_async(event: Dict[str, Any], db: Optional[Session] = None):
    # Issue: event is Dict[str, Any], very loose typing
    # Cache operations assume specific structure
    
    # Current: Relies on runtime validation
    # Better: Use typed event dict or model
    
    # Best practice:
    @dataclass
    class EventPayload:
        id: str
        user_id: Optional[str]
        status: str
        # ... other fields
    
    async def _save_event_async(event: EventPayload, db: Optional[Session] = None):
        # Now type-safe throughout
```

## Recommended Refactoring Strategy

### Phase 1: Quick Wins (30 min)
1. Add `import sqlalchemy as sa`
2. Fix return type annotations (compress/decompress)
3. Fix function signature (Optional[Session])
4. Add filename validation in upload_voice_note

### Phase 2: Type Guard Improvements (45 min)
1. Replace `if column:` with `if column is not None:`
2. Add proper None guards for optional returns
3. Extract query result IDs with explicit str() conversion
4. Ensure all async calls have await

### Phase 3: Column Assignment Fixes (20 min)
1. Use walrus operator for None checks
2. Add defaults where appropriate
3. Test ORM persistence

### Phase 4: Future Improvement (2+ hours)
1. Migrate models.py to SQLAlchemy 2.0 `Mapped[]` style
2. Create typed Event dataclass for internal use
3. Replace loose `Dict[str, Any]` with specific types
4. Add py.typed marker to package

## Testing Strategy

### Unit Tests Needed
```python
# Test _compress/_decompress with None
assert _compress(None) is None
assert _compress({}) == "c:..." + base64
assert _decompress(None) is None
assert _decompress("c:...") == {} or []

# Test SQLAlchemy assignments
event = {
    "id": uuid4(),
    "user_id": "user123",
    "status": "ACTIVE",
    # ... with None values
}
sos_record = SOSEvent()
await _async_persist(event)
assert sos_record.user_id == "user123"

# Test Optional returns
event_none = await _load_event_async("nonexistent", db)
assert event_none is None
if event_none:  # Type guard
    result = _map_event_to_res(event_none)
```

### Integration Tests Needed
```python
# Test Redis cache behavior
event = trigger_sos(payload)
cached = await cache.get(f"sos:event:{event['id']}")
assert cached is not None

# Test Column conditionals
sos = db.query(SOSEvent).first()
if sos.resolved_at is not None:
    iso_str = sos.resolved_at.isoformat()
    assert isinstance(iso_str, str)

# Test Query results
ids = [str(r.id) for r in db.query(SOSEvent).all()]
for event_id in ids:
    event = await _load_event_async(event_id, db)
    assert event is not None
```

## Summary

### Current State
- **Type System**: SQLAlchemy v1.x style Columns without type hints
- **Type Errors**: 22 errors in sos.py due to loose typing
- **Cache Design**: Async operations with proper error handling
- **ORM Usage**: Synchronous queries mixed with async handlers

### Risks Addressed
1. ✅ SQLAlchemy Column assignment safety (10 fixes)
2. ✅ Async/await consistency (2 fixes)
3. ✅ Optional type handling (2 fixes)
4. ✅ Query result type safety (4 fixes)

### Future Improvements
1. Migrate to SQLAlchemy v2.0 `Mapped[]` annotation style
2. Create typed dataclasses for Event payloads
3. Add runtime validation with Pydantic models
4. Implement stricter type checking with `mypy --strict`
