# Comprehensive Pylance Error Analysis: backend/api/sos.py

**Date**: April 16, 2026 | **Total Errors**: 22 | **Files Affected**: 3

---

## Executive Summary

The SOS module has **8 distinct error categories** stemming from:
1. **SQLAlchemy Column type system conflicts** (40% of errors)
2. **Missing async/await calls** (14% of errors)
3. **Return type mismatches** (9% of errors)
4. **Invalid boolean operations on Column objects** (9% of errors)
5. **Missing imports** (5% of errors)
6. **Optional type handling** (18% of errors)
7. **Path join with None values** (5% of errors)

Root cause: SQLAlchemy v2.x stricter typing + mixed async/sync Redis usage + defensive return patterns.

---

## Detailed Error Analysis

### ✅ CATEGORY 1: Return Type Mismatches (2 errors)
**Lines**: 108, 115  
**Functions**: `_compress()`, `_decompress()`

#### Error Details
```python
# Line 105-115
def _compress(data: Any) -> str:  # ❌ Error: returns None at line 108
    if not data: return None  # Type "None" is not assignable to return type "str"
    try:
        # ... compression code ...
        return "c:" + base64.b64encode(compressed).decode('utf-8')
    except Exception as e:
        logger.error(f"Compression error: {e}")
        return None  # ❌ Type "None" is not assignable to return type "str"
```

#### Root Cause
Defensive error handling returns `None`, but function signature declares `str` return. This is intentional but type-unsafe.

#### Fix
```python
def _compress(data: Any) -> Optional[str]:
    """Compress data using zlib and encode to base64 string."""
    if not data: 
        return None
    try:
        json_bytes = json.dumps(data).encode('utf-8')
        compressed = zlib.compress(json_bytes)
        return "c:" + base64.b64encode(compressed).decode('utf-8')
    except Exception as e:
        logger.error(f"Compression error: {e}")
        return None

def _decompress(compressed_str: Optional[str]) -> Any:
    """Decompress base64 string using zlib."""
    if not compressed_str or not compressed_str.startswith("c:"):
        return compressed_str
    try:
        raw_b64 = compressed_str[2:]
        compressed_bytes = base64.b64decode(raw_b64)
        json_bytes = zlib.decompress(compressed_bytes)
        return json.loads(json_bytes.decode('utf-8'))
    except Exception as e:
        logger.error(f"Decompression error: {e}")
        return None
```

---

### ✅ CATEGORY 2: SQLAlchemy Column Type Issues (10 errors)
**Lines**: 227, 230-236, 243, 246, 249, 252, 756-757  
**Core Problem**: SQLAlchemy v2.x type stubs declare column attributes as `Column[T]` not `T`

#### Error Details - Attribute Assignments

```python
# Line 227 - user_id assignment
sos_record.user_id = event.get("user_id")
# ❌ Expression of type "Any | None" cannot be assigned to attribute "user_id" 
#    Type "Any | None" is not assignable to type "Column[str]"

# Line 230-236 - Similar pattern for:
sos_record.category = event.get("category")  # ❌ Any | None → Column[str]
sos_record.extra = event.get("extra")         # ❌ Any | None → Column[str]
sos_record.name = event.get("name")           # ❌ Any | None → Column[str]
sos_record.phone = event.get("phone")         # ❌ Any | None → Column[str]
sos_record.email = event.get("email")         # ❌ Any | None → Column[str]
sos_record.lat = event.get("lat")             # ❌ Any | None → Column[Unknown]
sos_record.lng = event.get("lng")             # ❌ Any | None → Column[Unknown]

# Line 243 - JSON field
sos_record.trip_data = event.get("trip")      # ❌ Any | None → Column[Any]

# Lines 246, 249, 252 - DateTime fields
sos_record.triggered_at = datetime.fromisoformat(event["triggered_at"])
# ❌ datetime → Column[datetime]
```

#### Root Cause Analysis

SQLAlchemy's model definitions show:
```python
# From backend/database/models.py
class SOSEvent(UserBase):
    __tablename__ = "sos_events"
    id = Column(String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String(36), ForeignKey("users.id"), nullable=True)
    # ... etc
```

The issue: Pylance interprets `Column(...)` attributes as having type `Column[T]`, not the actual `T` value. This is technically correct from SQLAlchemy's descriptor perspective, but runtime behavior assigns the value to the column.

#### Solutions

**Solution A: Explicit None-Coalescing** (Recommended)
```python
sos_record.user_id = event.get("user_id") or ""
sos_record.category = event.get("category")
sos_record.extra = event.get("extra") or ""
sos_record.name = event.get("name") or ""
sos_record.phone = event.get("phone") or ""
sos_record.email = event.get("email") or ""
sos_record.lat = event.get("lat") or 0.0
sos_record.lng = event.get("lng") or 0.0
sos_record.trip_data = event.get("trip")
```

**Solution B: Explicit Conditionals** (Type-Safe)
```python
if (user_id := event.get("user_id")) is not None:
    sos_record.user_id = user_id
# DateTime fields with existing try-except:
if event.get("triggered_at"):
    try: 
        sos_record.triggered_at = datetime.fromisoformat(event["triggered_at"])
    except (ValueError, TypeError): 
        pass
```

**Solution C: Type Casting** (Most Explicit)
```python
from typing import cast
sos_record.user_id = cast(str, event.get("user_id"))
sos_record.category = cast(Optional[str], event.get("category"))
```

#### Additional Column Issues: Profile Attributes (Lines 756-757)

```python
# Line 756-757
prof.karma_score += 10  # ❌ ColumnElement[int] → Column[int]
prof.help_count += 1    # ❌ ColumnElement[int] → Column[int]
```

**Root Cause**: Arithmetic on Column objects returns `ColumnElement[int]`, not `int`.

**Fix**:
```python
prof.karma_score = (prof.karma_score or 0) + 10
prof.help_count = (prof.help_count or 0) + 1
```

---

### ✅ CATEGORY 3: Invalid Boolean Operations on Column Types (3 errors)
**Lines**: 300-301, 479  
**Core Problem**: SQLAlchemy Column's `__bool__()` returns `NoReturn` to prevent implicit coercion

#### Error Details

```python
# Line 300-301: From _load_event_async function
raw_event = {
    # ...
    "resolved_at": sos_record.resolved_at.isoformat() if sos_record.resolved_at else None,
    # ❌ Invalid conditional operand of type "Column[datetime]"
    #    Method __bool__ for type "Column[datetime]" returns type "NoReturn"
    
    "acknowledged_at": sos_record.acknowledged_at.isoformat() if sos_record.acknowledged_at else None
    # ❌ Same issue
}

# Line 479: From get_sos_by_pnr function
if r.trip_data and str(r.trip_data.get("pnr_number")) == str(pnr):
    # ❌ Invalid conditional operand of type "Column[Any] | bool"
```

#### Root Cause
SQLAlchemy intentionally blocks truthiness evaluation of Column objects because it's ambiguous whether you mean:
- "Is this field set?" (None check)
- "Is this field truthy?" (value check)
- "Is this column part of the query?" (state check)

#### Fixes

**For datetime comparisons**:
```python
"resolved_at": sos_record.resolved_at.isoformat() if sos_record.resolved_at is not None else None,
"acknowledged_at": sos_record.acknowledged_at.isoformat() if sos_record.acknowledged_at is not None else None,
```

**For trip_data check**:
```python
if r.trip_data is not None and isinstance(r.trip_data, dict) and str(r.trip_data.get("pnr_number")) == str(pnr):
    event = await _load_event_async(r.id, db)
    return _map_event_to_res(event)
```

---

### ✅ CATEGORY 4: Missing async/await Calls (2 errors)
**Lines**: 428, 494  
**Functions**: `get_incident_heatmap()`, `get_all_sos()`

#### Error Details

```python
# Line 428: In get_incident_heatmap()
import redis
from database.config import Config
sync_redis = redis.from_url(Config.REDIS_URL)
raw_ids = sync_redis.smembers(SOS_INDEX_KEY) or []
ids = [i.decode('utf-8') if isinstance(i, bytes) else i for i in raw_ids]
# ❌ "Awaitable[Set[Unknown]]" is not iterable - __iter__ method not defined

# Line 494: In get_all_sos()
# Same issue repeated
```

#### Root Cause
There's confusion in the code between:
- **`redis` (sync client)**: returns `Set[bytes]` synchronously
- **`redis.asyncio` (async client)**: returns `Awaitable[Set[bytes]]`

The code imports `redis` (sync) but Pylance is inferring `redis.asyncio` behavior (async).

#### Fix

Option 1: Use synchronous Redis properly:
```python
import redis
from database.config import Config

# In get_incident_heatmap():
if multi_layer_cache.redis:
    try:
        # Already sync - don't use await
        raw_ids = multi_layer_cache.redis.smembers(SOS_INDEX_KEY) or []
        ids = [i.decode('utf-8') if isinstance(i, bytes) else i for i in raw_ids]
    except Exception: 
        pass
```

Option 2: If using async Redis, await the call:
```python
if multi_layer_cache.redis:
    try:
        raw_ids = await multi_layer_cache.redis.smembers(SOS_INDEX_KEY) or []
        ids = [i.decode('utf-8') if isinstance(i, bytes) else i for i in raw_ids]
    except Exception: 
        pass
```

---

### ✅ CATEGORY 5: Column Types as Function Arguments (4 errors)
**Lines**: 437, 464, 480, 503  
**Functions**: Multiple DB query result handling

#### Error Details

```python
# Line 437: From get_incident_heatmap()
for eid in ids:
    e = await _load_event_async(eid, db)  # eid could be Column[str]
    # ❌ Argument of type "Column[str] | str | Unknown" cannot be assigned 
    #    to parameter "event_id" of type "str"

# Line 464: From get_sos_by_pnr()
event_id = sync_redis.get(f"{PNR_REGISTRY_KEY}:{pnr}")
if event_id:
    event_id = event_id.decode('utf-8') if isinstance(event_id, bytes) else event_id
    event = await _load_event_async(event_id, db)
    # ❌ event_id type is Awaitable[Any] | str (wrong type inference)

# Line 480: From get_sos_by_pnr()
for r in event_record:
    if r.trip_data is not None and isinstance(r.trip_data, dict):
        event = await _load_event_async(r.id, db)
        # ❌ r.id is Column[str] not str
```

#### Root Cause
Query results have Column types that need value extraction. The ORM's type system indicates these are Column descriptors, not raw values.

#### Fixes

**For query results**:
```python
# Ensure IDs are extracted properly from query results
active_records = db.query(SOSEvent).filter(SOSEvent.status.in_(["ACTIVE", "RESPONDING"])).all()
ids = [str(r.id) for r in active_records]  # Explicitly convert to string

# Later use:
for eid in ids:
    e = await _load_event_async(eid, db)  # Now eid is definitely str
```

**For redis.get() results**:
```python
event_id_bytes = sync_redis.get(f"{PNR_REGISTRY_KEY}:{pnr}")
if event_id_bytes:
    event_id = event_id_bytes.decode('utf-8') if isinstance(event_id_bytes, bytes) else event_id_bytes
    event = await _load_event_async(event_id, db)  # Now event_id is str
```

---

### ✅ CATEGORY 6: Missing Import (1 error)
**Line**: 472  
**Module**: SQLAlchemy operations

#### Error Details

```python
# Line 472: In get_sos_by_pnr()
event_record = db.query(SOSEvent).filter(
    sa.or_(  # ❌ "sa" is not defined
        SOSEvent.status == "ACTIVE",
        SOSEvent.status == "RESPONDING"
    )
).all()
```

#### Root Cause
Missing import for `sqlalchemy` as `sa` at module level.

#### Fix

Add at top of file (after other imports):
```python
import sqlalchemy as sa
```

Alternative: Use direct imports:
```python
from sqlalchemy import or_

# Then use:
event_record = db.query(SOSEvent).filter(
    or_(
        SOSEvent.status == "ACTIVE",
        SOSEvent.status == "RESPONDING"
    )
).all()
```

---

### ✅ CATEGORY 7: Optional Type Not Handled (2 errors)
**Lines**: 481, 464  
**Related**: Optional return from async function

#### Error Details

```python
# Line 464: In get_sos_by_pnr()
event = await _load_event_async(event_id, db)  # Returns Optional[Dict]

# Line 481: Using result without None check
if event and event.get("status") in ["active", "responding"]:
    return _map_event_to_res(event)
    # ❌ Argument of type "Dict[str, Any] | None" cannot be assigned 
    #    to parameter "e" of type "Dict[str, Any]"
```

#### Root Cause
Function signature `_load_event_async() -> Optional[Dict[str, Any]]` returns None in failure path, but `_map_event_to_res()` expects non-optional Dict.

#### Fix

```python
# Explicit None guard
event = await _load_event_async(event_id, db)
if event is not None and event.get("status") in ["active", "responding"]:
    return _map_event_to_res(event)

# Or at call site:
event = await _load_event_async(event_id, db)
if not event:
    raise HTTPException(status_code=404, detail="No active SOS for this PNR.")
return _map_event_to_res(event)  # Now guaranteed non-None
```

---

### ✅ CATEGORY 8: Path Join with None (1 error)
**Line**: 828  
**Function**: `upload_voice_note()`

#### Error Details

```python
# Line 828: In upload_voice_note()
file_path = os.path.join(event_media_dir, file.filename)
# ❌ Argument of type "str | None" cannot be assigned to parameter "paths" 
#    of type "StrPath" in function "join"
```

#### Root Cause
`UploadFile.filename` is `Optional[str]` (can be None if not provided).

#### Fix

```python
@router.post("/{event_id}/voice-note")
async def upload_voice_note(event_id: str, file: UploadFile = File(...), db: Session = Depends(get_db)):
    event = await _load_event_async(event_id, db)
    if not event:
        raise HTTPException(status_code=404)
    
    # Validate filename
    if not file.filename:
        raise HTTPException(status_code=400, detail="Invalid filename")
    
    event_media_dir = os.path.join(MEDIA_DIR, event_id)
    os.makedirs(event_media_dir, exist_ok=True)
    
    # Now filename is guaranteed non-None
    file_path = os.path.join(event_media_dir, file.filename)
    
    with open(file_path, "wb") as buffer:
        shutil.copyfileobj(file.file, buffer)
    
    if "chat_history" not in event:
        event["chat_history"] = []
    
    event["chat_history"].append({
        "sender": "user",
        "type": "voice_note",
        "content": "[VOICE NOTE]",
        "media_url": f"/media/sos/{event_id}/{file.filename}",
        "timestamp": datetime.utcnow().isoformat()
    })
    
    await _save_event_async(event)
    await manager.broadcast_sos(event)
    return {"status": "uploaded"}
```

---

## Implementation Priority

### Phase 1: Critical (Blocking Other Fixes)
1. **Add SQLAlchemy import** (line 1)
   ```python
   import sqlalchemy as sa
   ```

2. **Fix return type annotations** (lines 105, 118)
   ```python
   def _compress(data: Any) -> Optional[str]:
   def _decompress(compressed_str: Optional[str]) -> Any:
   ```

3. **Fix function signature** (line 185)
   ```python
   async def _save_event_async(event: Dict[str, Any], db: Optional[Session] = None):
   ```

### Phase 2: Major Issues (Affects Multiple Functions)
4. **SQLAlchemy Column assignments** (lines 227-236, 243, 246, 249, 252, 756-757)
5. **DateTime conditionals** (lines 300-301)
6. **Trip data conditional** (line 479)

### Phase 3: Functional Issues
7. **Async/await fixes** (lines 428, 494)
8. **Function argument type guards** (lines 437, 480, 503)
9. **Optional return guards** (lines 464, 481)

### Phase 4: Validation
10. **File upload filename validation** (line 828)

---

## Files Requiring Modifications

### 1. **backend/api/sos.py** (PRIMARY)
- Import: `sqlalchemy as sa`
- 15+ type fixes for Column assignments
- 3 async/await guards
- 4 function argument type guards
- 2 optional return guards
- 1 filename validation

### 2. **backend/database/models.py** (REFERENCE)
- Already has `py.typed` requirements
- May need to add type comments for Column fields if Pylance doesn't recognize

### 3. **backend/services/emergency/alert_manager.py** (REFERENCE)
- Verify return types are consistent
- No changes needed if return type is `Dict[str, Any]`

---

## Type System Notes

### SQLAlchemy v2.x Typing Strategy
The new SQLAlchemy typing strictly distinguishes:
- **Column Definition**: `Column[T]` - the descriptor
- **Runtime Value**: `T` - the actual value in the instance
- **Database NULL**: `None` - represented as Python None

### Best Practices Going Forward

1. **Use Type Narrowing**:
   ```python
   value = record.column
   if value is not None:
       # Type narrowing: value is now T, not Column[T]
   ```

2. **Use Walrus Operator**:
   ```python
   if (val := record.column) is not None:
       use(val)
   ```

3. **Explicit Casting When Needed**:
   ```python
   from typing import cast
   val = cast(str, record.user_id)
   ```

4. **Query Result Processing**:
   ```python
   # Option 1: Use list comprehension with str()
   ids = [str(r.id) for r in results]
   
   # Option 2: Use scalar results
   ids = db.query(SOSEvent.id).filter(...).scalars().all()
   ```

---

## Testing Checklist

- [ ] Import `sqlalchemy as sa` resolves undefined reference
- [ ] Return types on compress/decompress functions accept Optional
- [ ] SQLAlchemy column assignments with defaults don't throw type errors
- [ ] DateTime fields use `.isoformat()` safely
- [ ] Column boolean checks use `is not None` pattern
- [ ] Redis calls work with sync client (no await needed)
- [ ] Function arguments receive properly typed values from DB queries
- [ ] Optional returns are properly guarded before use
- [ ] File uploads validate filename before path.join
- [ ] All Pylance errors resolve to 0

---

## Summary Table

| Category | Count | Lines | Severity | Effort |
|----------|-------|-------|----------|--------|
| Return Type Mismatch | 2 | 108, 115 | Low | 5 min |
| Column Type Issues | 10 | 227-236,243,246,249,252,756-757 | High | 20 min |
| Invalid Conditionals | 3 | 300-301, 479 | Medium | 10 min |
| Missing Async/Await | 2 | 428, 494 | Medium | 10 min |
| Arg Type Mismatches | 4 | 437,464,480,503 | Medium | 15 min |
| Missing Import | 1 | 472 | Critical | 1 min |
| Optional Not Handled | 2 | 464, 481 | Medium | 10 min |
| Path Join with None | 1 | 828 | Low | 5 min |
| **TOTAL** | **22** | - | - | **~76 min** |

---

## Next Steps
1. Apply fixes in priority order (Phase 1-4)
2. Run Pylance check after each batch
3. Execute test suite to verify functionality
4. Document any architectural changes needed
