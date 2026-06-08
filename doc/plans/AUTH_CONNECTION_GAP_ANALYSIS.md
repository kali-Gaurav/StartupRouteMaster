# Frontend-Backend Auth Connection Gap Analysis & Implementation Plan

## Current Status

### ✅ Implemented
- Supabase client initialized (frontend)
- AuthContext with Supabase integration (frontend)
- `get_current_user` dependency with Supabase token validation (backend)
- Supabase client configured in backend
- API client with auth header injection (frontend)
- CORS middleware enabled (backend)

### ❌ Gaps Identified

#### 1. **Backend Token Validation Error Handling** ⚠️ CRITICAL
**Problem**: If token validation fails in `get_current_user`, exception handling may not return proper 401/403
**Impact**: Auth failures may return 500 instead of 401, breaking token refresh logic
**Solution Needed**:
- Add explicit `HTTPException(status_code=401)` in token validation
- Return `{"error": "Invalid or expired token", "code": "INVALID_TOKEN"}` 
- Add token refresh endpoint

**File**: `backend/api/dependencies.py` - Lines 49-52

#### 2. **Missing Auth Refresh Endpoint** ⚠️ HIGH
**Problem**: Frontend can get 401 but has no way to refresh token
**Impact**: Users must re-login after logout when session expires
**Solution Needed**:
- Add `/api/v2/auth/refresh` POST endpoint in new `backend/api/v2/auth_refresh.py`
- Accept refresh token, return new access token
- Integration with Supabase session refresh

**File**: Need to create `backend/api/v2/auth_refresh.py`

#### 3. **Supabase JWT Secret Not Used for Verification** ⚠️ HIGH
**Problem**: Backend doesn't verify JWT signature locally, relies on Supabase API call
**Impact**: 
  - Extra API calls to Supabase for every request
  - Higher latency
  - Dependency on Supabase availability
**Solution Needed**:
- Add local JWT verification using `SUPABASE_JWT_SECRET`
- Create `backend/utils/security.py` function `verify_supabase_jwt(token: str) -> dict`
- Use as fallback if Supabase API fails

**File**: Need to improve `backend/utils/security.py`

#### 4. **No Logout Token Blacklist** ⚠️ MEDIUM
**Problem**: Logged-out tokens can still be used until they expire
**Impact**: Security vulnerability - old tokens can be replayed
**Solution Needed**:
- Implement Redis-based token blacklist on logout
- Check blacklist in `get_current_user` (already partially done)
- Set TTL to token expiry time

**File**: Update `backend/api/dependencies.py` - `get_current_user` function

#### 5. **Missing CORS Preflight Validation** ⚠️ MEDIUM
**Problem**: Browser may not send credentials with cross-origin requests
**Impact**: Token not sent in Authorization header
**Solution Needed**:
- Verify CORS allows `Authorization` header
- Response should include `Access-Control-Allow-Credentials: true`
- Verify frontend uses `credentials: 'include'` in fetch

**File**: `backend/app.py` - CORS middleware config

#### 6. **Supabase Session Not Persisted** ⚠️ LOW
**Problem**: Frontend session lost on page refresh
**Impact**: User needs to re-login after refresh (bad UX)
**Solution Needed**:
- Supabase automatically persists to localStorage
- But need to ensure persistence is enabled in supabase client
- Add session recovery on app init

**File**: `frontend/src/context/AuthContext.tsx` - useEffect hook

#### 7. **No Protected Route Guard** ⚠️ MEDIUM
**Problem**: User can navigate to protected routes even when not authenticated
**Impact**: UI shows login-protected content, then errors
**Solution Needed**:
- Create `ProtectedRoute` component that checks `isAuthenticated`
- Redirect to `/login` if not authenticated
- Show loading state while checking auth

**File**: Need to create `frontend/src/components/ProtectedRoute.tsx`

#### 8. **Missing User Sync on Login** ⚠️ MEDIUM
**Problem**: Supabase user data not synced to backend profile table
**Impact**: User profile incomplete on backend
**Solution Needed**:
- After login, call POST `/v2/user/profile/sync` with user metadata
- Trigger from LoginPage.tsx after successful sign-in
- Update local profile with server response

**File**: `frontend/src/pages/auth/LoginPage.tsx` - Add sync call after login

#### 9. **No MFA / Email Verification** ⚠️ LOW (Upgrade Later)
**Problem**: Supabase MFA not configured
**Impact**: Less secure for production
**Solution Needed**: After MVP
- Enable Supabase MFA in database
- Add MFA UI to LoginPage
- Handle MFA redirect flow

#### 10. **Backend User Creation Race Condition** ⚠️ MEDIUM
**Problem**: Multiple concurrent requests could create duplicate users
**Impact**: Data inconsistency
**Solution Needed**:
- Add unique constraint on supabase_id
- Use database-level constraint
- Handle integrity error gracefully

**File**: `backend/database/models.py`

---

## Implementation Priority

### Phase 1 (Blocking - Fix Now)
1. ✅ Backend token validation error handling (Gap #1)
2. ❌ Backend auth refresh endpoint (Gap #2)
3. ❌ Local JWT verification (Gap #3)

### Phase 2 (Important)
4. ❌ Logout token blacklist (Gap #4)
5. ❌ Protected route guard (Gap #7)
6. ❌ User sync on login (Gap #8)

### Phase 3 (Polish)
7. ❌ Session persistence verification (Gap #6)
8. ❌ CORS validation (Gap #5)
9. ❌ MFA setup (Gap #9)
10. ❌ Race condition handling (Gap #10)

---

## Testing Checklist

### Before Implementation
- [ ] Backend running on port 8000
- [ ] Frontend can reach /health endpoint
- [ ] Supabase credentials valid

### After Each Gap Fix
- [ ] Run `npm run test` in frontend
- [ ] Manually test login flow
- [ ] Check browser console for errors
- [ ] Verify auth tokens in Network tab
- [ ] Test token expiry (wait 1 hour or mock)
- [ ] Test logout and re-login
- [ ] Test protected route redirect

---

## API Endpoint Checklist

### Frontend Calls
- [ ] GET  /health                     (no auth needed)
- [ ] POST /v2/auth/signup              (Supabase, no backend auth needed initially)
- [ ] POST /v2/auth/login               (Supabase)
- [ ] POST /v2/auth/logout              (backend - needs token)
- [ ] POST /v2/auth/refresh             (backend - needs refresh token) **TODO**
- [ ] GET  /v2/user/profile             (backend - needs access token)
- [ ] POST /v2/user/profile/sync        (backend - needs access token)
- [ ] POST /v2/search/unified           (backend - needs access token)
- [ ] POST /v2/booking/search           (backend - needs access token)
- [ ] POST /v2/booking/initiate         (backend - needs access token)

### Environment Variables Needed

#### Frontend (.env or production.frontend.env)
```env
VITE_SUPABASE_URL=https://bkzrxgtsfovctfviqkuh.supabase.co
VITE_SUPABASE_ANON_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
VITE_RAILWAY_API_URL=http://localhost:8000        # or production URL
```

#### Backend (.env)
```env
SUPABASE_URL=https://bkzrxgtsfovctfviqkuh.supabase.co
SUPABASE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_SERVICE_KEY=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9...
SUPABASE_JWT_SECRET=3L0kvbdACG1I85UEORQUaW51F6bQhOIQUI+xEFTZep3JBvKVbcjMcgsIskheS19wVCN2GSWABFLJp43DJvUew==
```

---

## Summary

**Total Gaps Found**: 10
- Critical: 1
- High: 3
- Medium: 4
- Low: 2

**Estimated Implementation Time**: 
- Phase 1: 2-3 hours
- Phase 2: 3-4 hours
- Phase 3: 2-3 hours

**Next Steps**:
1. Review this gap analysis
2. Approve implementation plan
3. Begin Phase 1 implementation
