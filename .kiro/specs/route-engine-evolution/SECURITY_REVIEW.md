# Route Engine Evolution - Security Review

**Review Date:** 2026-05-08  
**Reviewer:** CIPHER (Security Lead)  
**Status:** 🔴 NEEDS FIXES  
**Severity:** HIGH

---

## Executive Summary

The Route Engine Evolution Tier 1 features have several security gaps that must be addressed before production deployment. Critical issues include missing authentication on SSE endpoints, lack of rate limiting, and potential information disclosure in error messages.

**Risk Score:** 7.5/10 (High)  
**Issues Found:** 8  
**Critical:** 2  
**High:** 4  
**Medium:** 2

---

## Findings

### 🔴 CRITICAL-01: Missing Authentication on SSE Endpoints

**Severity:** Critical  
**Status:** 🔴 OPEN

**Description:**  
The SSE streaming endpoint (`/routes/search/stream`) does not require JWT authentication. Any user can initiate a route search stream without authentication.

**Affected Endpoint:**
```
GET /api/v1/routes/search/stream
```

**Impact:**
- Unauthorized access to route search functionality
- Potential abuse of streaming connections
- Exposure of route data to unauthenticated users

**Evidence:**
```python
@sse_router.get("/search/stream")
async def stream_route_search(
    request: Request,
    source: str,
    destination: str,
    # No authentication decorator or dependency
):
```

**Recommendation:**
```python
from backend.api.middleware.auth import get_current_user

@sse_router.get("/search/stream")
async def stream_route_search(
    request: Request,
    current_user: dict = Depends(get_current_user),  # Add auth
    source: str = Query(...),
    ...
):
```

**Fix Priority:** P0 - Must fix before production

---

### 🔴 CRITICAL-02: No Rate Limiting on Route Endpoints

**Severity:** Critical  
**Status:** 🔴 OPEN

**Description:**  
Route search endpoints lack rate limiting, allowing potential abuse through automated requests.

**Affected Endpoints:**
- `GET /api/v1/routes/quick`
- `POST /api/v1/routes/search`
- `GET /api/v1/routes/search/stream`
- `POST /api/v1/routes/qpo/analyze`

**Impact:**
- Denial of service through request flooding
- Increased infrastructure costs from abuse
- Degraded service for legitimate users

**Recommendation:**
Implement rate limiting using FastAPI-Limiter:

```python
from fastapi_limiter import Limiter
from fastapi_limiter.depends import RateLimiter

limiter = Limiter(key_func=get_user_ip)

@api_router.get("/routes/quick", dependencies=[Depends(RateLimiter(times=100, minutes=1))])
async def quick_route_search(...):
```

**Fix Priority:** P0 - Must fix before production

---

### 🟠 HIGH-01: Input Validation Gaps

**Severity:** High  
**Status:** 🟠 IN PROGRESS

**Description:**  
Station codes are not validated before use, allowing potentially malicious input.

**Current Code:**
```python
async def stream_route_search(
    source: str,
    destination: str,
    travel_date: str,
    # No validation of station code format
):
    if not source or not destination:
        raise HTTPException(status_code=400, detail="Source and destination are required")
```

**Issues:**
- Station codes can be any string (no regex validation)
- SQL injection possible if used directly in queries
- XSS possible if reflected in responses

**Recommendation:**
```python
import re

STATION_CODE_PATTERN = re.compile(r'^[A-Z]{2,5}$')

def validate_station_code(code: str, field: str) -> str:
    if not STATION_CODE_PATTERN.match(code):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {field}: must be 2-5 uppercase letters"
        )
    return code

# Usage:
validate_station_code(source, "source")
validate_station_code(destination, "destination")
```

**Fix Priority:** P1 - Should fix before production

---

### 🟠 HIGH-02: Error Message Information Disclosure

**Severity:** High  
**Status:** 🔴 OPEN

**Description:**  
Error messages may expose internal implementation details, database structures, or stack traces.

**Current Code:**
```python
except Exception as e:
    logger.error(f"Error streaming routes for {connection_id}: {e}")
    yield self._create_event(
        event_type=EventType.ERROR,
        data={
            "status": "error",
            "message": str(e),  # Exposes internal error
            "error_type": type(e).__name__
        }
    )
```

**Impact:**
- Information disclosure about internal systems
- Helps attackers understand database schema
- Exposes library/framework versions

**Recommendation:**
```python
except Exception as e:
    logger.error(f"Error streaming routes for {connection_id}: {e}")
    yield self._create_event(
        event_type=EventType.ERROR,
        data={
            "status": "error",
            "message": "An error occurred while processing your request",
            "error_id": generate_error_id()  # For logging correlation
        }
    )
    # Log full error internally
    logger.exception(f"Route search error {generate_error_id()}: {e}")
```

**Fix Priority:** P1 - Should fix before production

---

### 🟠 HIGH-03: Missing CORS Configuration

**Severity:** High  
**Status:** 🔴 OPEN

**Description:**  
SSE endpoints lack proper CORS configuration, which may cause issues for frontend integration.

**Impact:**
- Cross-origin requests may be blocked
- Frontend on different domain cannot access API
- Potential security misconfiguration

**Recommendation:**
```python
from fastapi.middleware.cors import CORSMiddleware

app.add_middleware(
    CORSMiddleware,
    allow_origins=["https://routemaster.in", "https://www.routemaster.in"],
    allow_credentials=True,
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)
```

**Fix Priority:** P1 - Should fix before production

---

### 🟠 HIGH-04: Connection ID Predictability

**Severity:** High  
**Status:** 🔴 OPEN

**Description:**  
Connection IDs are predictable, which could allow session hijacking.

**Current Code:**
```python
connection_id = f"{source}-{destination}-{datetime.utcnow().timestamp()}"
```

**Impact:**
- Predictable IDs make session prediction easier
- Could allow access to other users' streams

**Recommendation:**
```python
import secrets

connection_id = f"{source}-{destination}-{secrets.token_hex(16)}"
```

**Fix Priority:** P1 - Should fix before production

---

### 🟡 MEDIUM-01: Missing Request Timeout

**Severity:** Medium  
**Status:** 🟡 ACKNOWLEDGED

**Description:**  
Long-running SSE streams could tie up server resources.

**Current Configuration:**
```python
config = StreamConfig(
    stream_timeout_seconds=30  # Already has timeout
)
```

**Status:** ✅ Already addressed in configuration

---

### 🟡 MEDIUM-02: No Request Size Limits

**Severity:** Medium  
**Status:** 🔴 OPEN

**Description:**  
Batch search endpoint doesn't limit request size.

**Recommendation:**
```python
from fastapi import Body

@api_router.post("/routes/batch", limit_request_size=1000)
async def batch_route_search(
    queries: List[Dict[str, str]] = Body(..., max_items=100)
):
```

**Fix Priority:** P2 - Should fix before production

---

## Security Checklist

| Category | Item | Status | Priority |
|----------|------|--------|----------|
| Authentication | JWT required on all endpoints | 🔴 OPEN | P0 |
| Authentication | SSE endpoint auth | 🔴 OPEN | P0 |
| Rate Limiting | Per-user rate limits | 🔴 OPEN | P0 |
| Rate Limiting | Global rate limits | 🔴 OPEN | P0 |
| Input Validation | Station code format | 🟠 IN PROGRESS | P1 |
| Input Validation | Travel date format | 🔴 OPEN | P1 |
| Error Handling | Sanitized error messages | 🔴 OPEN | P1 |
| CORS | Configured allowed origins | 🔴 OPEN | P1 |
| Session Security | Random connection IDs | 🔴 OPEN | P1 |
| Request Limits | Batch size limits | 🔴 OPEN | P2 |
| Logging | Audit logging | 🔴 OPEN | P1 |

---

## Recommended Security Middleware

```python
# backend/api/middleware/security.py

from fastapi import Request, HTTPException
from fastapi.responses import JSONResponse
from slowapi import Limiter
from slowapi.util import get_remote_address
import re
import secrets

# Rate limiter
limiter = Limiter(key_func=get_remote_address)

# Station code validation
STATION_CODE_PATTERN = re.compile(r'^[A-Z]{2,5}$')

def validate_station_code(code: str, field: str) -> str:
    if not code or not STATION_CODE_PATTERN.match(code):
        raise HTTPException(
            status_code=400,
            detail=f"Invalid {field}: must be 2-5 uppercase letters"
        )
    return code

# Secure connection ID generator
def generate_secure_connection_id(prefix: str = "conn") -> str:
    return f"{prefix}-{secrets.token_hex(16)}"

# Sanitized error handler
async def security_exception_handler(request: Request, exc: Exception):
    logger.error(f"Security exception: {exc}")
    return JSONResponse(
        status_code=400,
        content={
            "error": "Invalid request",
            "message": "Your request could not be processed"
        }
    )
```

---

## Action Items

| ID | Action | Owner | Due Date | Status |
|----|--------|-------|----------|--------|
| SEC-01 | Add JWT authentication to all route endpoints | SIGMA | 2026-05-09 | 🔴 OPEN |
| SEC-02 | Implement rate limiting (100 req/min) | SIGMA | 2026-05-09 | 🔴 OPEN |
| SEC-03 | Add station code validation regex | SIGMA | 2026-05-09 | 🟠 IN PROGRESS |
| SEC-04 | Sanitize error messages | SIGMA | 2026-05-10 | 🔴 OPEN |
| SEC-05 | Configure CORS for frontend domains | SIGMA | 2026-05-10 | 🔴 OPEN |
| SEC-06 | Use secure random for connection IDs | SIGMA | 2026-05-10 | 🔴 OPEN |
| SEC-07 | Add request size limits to batch endpoint | SIGMA | 2026-05-11 | 🔴 OPEN |
| SEC-08 | Add audit logging for security events | SIGMA | 2026-05-11 | 🔴 OPEN |

---

## Testing Recommendations

1. **Authentication Testing**
   - Verify all endpoints reject requests without JWT
   - Test expired token handling
   - Test token with insufficient permissions

2. **Rate Limiting Testing**
   - Send >100 requests in 1 minute
   - Verify 429 response after limit
   - Test rate limit reset behavior

3. **Input Validation Testing**
   - Send invalid station codes
   - Send SQL injection payloads
   - Send XSS payloads in parameters

4. **Error Handling Testing**
   - Trigger various error conditions
   - Verify error messages don't leak info
   - Check error response format

---

## Sign-off Required

- [ ] **CIPHER** - Security Review Complete
- [ ] **NEXUS** - Architecture Approval
- [ ] **ARIA** - Production Go-Ahead

---

**Document Version:** 1.0  
**Next Review:** 2026-05-15 (after fixes)