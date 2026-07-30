# FEATURE #2: USER DASHBOARD — REFINED IMPLEMENTATION SPEC

**Based on:** Deep codebase analysis  
**Status:** Ready to implement  
**Estimated Time:** 3-4 hours  
**Target Completion:** This session (after Feature #1)

---

## PART A: ANALYSIS FINDINGS → SPEC

### What Already Exists (Don't Recreate)
✅ **Frontend UI Components** (UserDashboard.tsx, 700+ lines)
- Dashboard summary cards (4 stats)
- Booking history table
- Responsive grid layout
- Status badges and icons
- Action buttons structure
- Skeleton loading components

✅ **API Endpoints** (backend/api/booking_routes.py)
- GET /api/v1/bookings/v1/user/dashboard
- GET /api/v1/bookings/v1/user/bookings  
- GET /api/v1/bookings/v1/user/payments
- GET /api/v1/bookings/v1/user/tickets
- GET /api/v1/bookings/v1/user/profile

✅ **Backend Service Methods** (BookingService class)
- get_dashboard_summary()
- get_user_bookings()
- get_user_payments()
- get_user_tickets()
- get_user_profile()

✅ **Database Schema**
- Booking table (with all fields)
- Payment table (linked)
- User table (relationships)
- BookingAuditLog (tracking)

### Critical Issues Found (Must Fix)

| Issue | Location | Impact | Fix |
|-------|----------|--------|-----|
| **Duplicated /v1 prefix** | Endpoint paths | API won't be found | Remove /v1/bookings/ prefix from routes |
| **No frontend-backend wire** | useBookings hook | Components don't show data | Implement API client calls |
| **Incomplete filtering** | Dashboard UI | Can't filter by date/status | Add filter logic |
| **No pagination controls** | Dashboard UI | Can't navigate results | Add next/prev buttons |
| **Saved routes missing** | Dashboard section | Feature incomplete | Build component |
| **Profile editing missing** | Profile section | Can't edit profile | Add form and submit |

### What's Missing (Must Build)

| Component | Location | Status | Action |
|-----------|----------|--------|--------|
| **API Client Integration** | frontend/src/api/ | 🔴 Missing | Create dashboard API client |
| **Filter Implementation** | Dashboard filtering | 🔴 Missing | Add status/date filters |
| **Pagination Logic** | Dashboard controls | 🔴 Missing | Add offset/limit |
| **Saved Routes Display** | Dashboard section | 🔴 Missing | Create component |
| **Profile Editor** | User profile section | 🔴 Missing | Create edit form |
| **Real-time Updates** | Dashboard refresh | 🔴 Missing | Add polling/WebSocket |
| **Error Handling** | Dashboard flow | 🟡 Partial | Add error boundaries |
| **Loading States** | Dashboard sections | 🟡 Partial | Show skeletons properly |

---

## PART B: IMPLEMENTATION SPEC

### DECISION #1: Fix API Endpoint Paths

**Current Problem:**
```
Routes defined as: GET /api/v1/bookings/v1/user/dashboard
Should be:         GET /api/v1/user/dashboard
```

The router has `prefix="/api/v1/bookings"` and endpoints have `@router.get("/v1/user/dashboard")` resulting in duplicated prefix.

**Solution:** Remove `/v1/bookings` from endpoint paths (leave as `/user/dashboard`, etc)

---

### DECISION #2: Frontend-Backend Integration Strategy

**Current State:** Components built, API not connected

**Approach:**
1. Create `useDashboardSummary()` hook for stats
2. Wire `useBookings()` hook to API endpoint
3. Create `useUserPayments()` hook for payment history
4. Create `useSavedRoutes()` hook (for saved routes)

**Pattern:** Follow Zustand + React Hooks pattern from Feature #1

---

### DECISION #3: Filtering & Sorting

**User Needs:**
- Filter bookings by status (upcoming, completed, cancelled)
- Filter by date range
- Sort by date (ascending/descending)
- Sort by amount (ascending/descending)

**Implementation:**
- Store filters in React state (or Zustand if stateful)
- Pass to API as query parameters
- Add UI controls (dropdown, date picker, sort buttons)

---

### DECISION #4: Pagination

**Current:** UserDashboard fetches first 50 bookings

**Spec:**
- Show 10 items per page
- Add "Previous" / "Next" buttons
- Show "Page X of Y"
- Preserve filters when paginating

---

### DECISION #5: Saved Routes Feature

**Current State:** UI structure exists but not functional

**Implementation:**
- Add component to display saved routes (array of origin → destination)
- Add "Add to Saved" button on search results
- Add "Remove" button on saved routes
- Store in localStorage or database

**Time Estimate:** 30 minutes

---

## PART C: FILES TO CREATE/MODIFY

### Backend Files

#### 1. FIX: `backend/api/booking_routes.py` (CRITICAL)
**Change 1:** Fix endpoint paths (Line 283)
```python
# BEFORE:
@router.get("/v1/user/dashboard")

# AFTER:
@router.get("/user/dashboard")

# BEFORE:
@router.get("/v1/user/bookings")

# AFTER:
@router.get("/user/bookings")

# (Repeat for all /v1/user/* endpoints)
```

**Reason:** Router prefix is already `/api/v1/bookings`, adding `/v1` again creates `/api/v1/bookings/v1/user/*`

#### 2. VERIFY: `backend/services/booking/service.py`
- Verify `get_dashboard_summary()` works
- Verify `get_user_bookings()` works
- Verify `get_user_payments()` works
- Add query parameter handling (filters, sorting)
- Add pagination support (offset, limit)

#### 3. ADD: `backend/schemas/dashboard.py` (NEW)
```python
class DashboardSummary(BaseModel):
    total_bookings: int
    total_spent: float
    upcoming_bookings: int
    cancelled_bookings: int
    recent_activity: List[dict]

class BookingFilter(BaseModel):
    status: Optional[str] = None  # upcoming, completed, cancelled
    date_from: Optional[str] = None  # YYYY-MM-DD
    date_to: Optional[str] = None  # YYYY-MM-DD
    sort_by: Optional[str] = "date"  # date, amount
    sort_order: Optional[str] = "desc"  # asc, desc
    offset: int = 0
    limit: int = 10
```

### Frontend Files

#### 1. CREATE: `frontend/src/api/dashboardApi.ts` (NEW)
```typescript
export async function getDashboardSummary(token: string) {
  const response = await fetch(`${API_BASE}/api/v1/user/dashboard`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  return response.json();
}

export async function getUserBookings(token: string, filters: BookingFilter) {
  const query = new URLSearchParams(filters);
  const response = await fetch(
    `${API_BASE}/api/v1/user/bookings?${query}`,
    { headers: { Authorization: `Bearer ${token}` } }
  );
  return response.json();
}

export async function getUserPayments(token: string) {
  const response = await fetch(`${API_BASE}/api/v1/user/payments`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  return response.json();
}

export async function getSavedRoutes(token: string) {
  const response = await fetch(`${API_BASE}/api/v1/user/saved-routes`, {
    headers: { Authorization: `Bearer ${token}` }
  });
  return response.json();
}
```

#### 2. CREATE: `frontend/src/hooks/useDashboardSummary.ts` (NEW)
```typescript
export function useDashboardSummary() {
  const { token } = useAuth();
  const [summary, setSummary] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);

  useEffect(() => {
    if (!token) return;
    (async () => {
      setLoading(true);
      try {
        const data = await getDashboardSummary(token);
        setSummary(data);
      } catch (err) {
        setError(err.message);
      } finally {
        setLoading(false);
      }
    })();
  }, [token]);

  return { summary, loading, error };
}
```

#### 3. UPDATE: `frontend/src/pages/UserDashboard.tsx`
```typescript
// Add imports
import { useDashboardSummary } from "@/hooks/useDashboardSummary";
import { getDashboardSummary } from "@/api/dashboardApi";

// Update to use hooks
function UserDashboard() {
  const { summary, loading: summaryLoading } = useDashboardSummary();
  const { data: bookings, loading: bookingsLoading } = useBookings({ limit: 10 });
  const [currentPage, setCurrentPage] = useState(1);
  const [statusFilter, setStatusFilter] = useState("all");
  
  // ... wire data to components
}
```

#### 4. CREATE: `frontend/src/components/SavedRoutes.tsx` (NEW)
```typescript
export function SavedRoutes() {
  const [routes, setRoutes] = useState([]);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    // Fetch from API or localStorage
    const saved = JSON.parse(localStorage.getItem("saved_routes") || "[]");
    setRoutes(saved);
  }, []);

  return (
    <div>
      <h3>Saved Routes</h3>
      {routes.map(route => (
        <div key={route.id}>
          {route.from} → {route.to}
          <button onClick={() => removeRoute(route.id)}>Remove</button>
        </div>
      ))}
    </div>
  );
}
```

#### 5. CREATE: `frontend/src/components/BookingFilters.tsx` (NEW)
```typescript
export function BookingFilters({ onFilter }: { onFilter: (filters) => void }) {
  const [status, setStatus] = useState("all");
  const [sortBy, setSortBy] = useState("date");

  return (
    <div>
      <select value={status} onChange={(e) => {
        setStatus(e.target.value);
        onFilter({ status: e.target.value });
      }}>
        <option value="all">All</option>
        <option value="upcoming">Upcoming</option>
        <option value="completed">Completed</option>
        <option value="cancelled">Cancelled</option>
      </select>

      <select value={sortBy} onChange={(e) => {
        setSortBy(e.target.value);
        onFilter({ sort_by: e.target.value });
      }}>
        <option value="date">Sort by Date</option>
        <option value="amount">Sort by Amount</option>
      </select>
    </div>
  );
}
```

### Test Files

#### 1. CREATE: `frontend/src/__tests__/integration/dashboard.test.tsx`
```typescript
describe("User Dashboard", () => {
  it("should display summary statistics", async () => {
    // Test summary cards
  });

  it("should display booking history", async () => {
    // Test booking list
  });

  it("should filter bookings by status", async () => {
    // Test filtering
  });

  it("should paginate bookings", async () => {
    // Test pagination
  });
});
```

---

## PART D: IMPLEMENTATION CHECKLIST

### Backend Implementation
- [ ] Fix endpoint paths (remove duplicated /v1)
- [ ] Verify service methods work correctly
- [ ] Add filter/sort query parameter handling
- [ ] Add pagination (offset/limit)
- [ ] Create DashboardSummary schema
- [ ] Test endpoints with curl
- [ ] Add error handling
- [ ] Add logging

### Frontend Implementation
- [ ] Create dashboardApi client
- [ ] Create useDashboardSummary hook
- [ ] Wire dashboard summary to UI
- [ ] Wire booking list to API
- [ ] Add status filter dropdown
- [ ] Add sort controls
- [ ] Add pagination buttons
- [ ] Create SavedRoutes component
- [ ] Complete profile section
- [ ] Add refresh button
- [ ] Add error boundaries
- [ ] Test with mock data

### Testing
- [ ] Unit tests for API clients
- [ ] Integration tests for dashboard flow
- [ ] Test error scenarios
- [ ] Test loading states
- [ ] Test mobile responsiveness
- [ ] Test filtering and pagination

### Documentation
- [ ] Update API documentation
- [ ] Update architecture guide
- [ ] Add component documentation
- [ ] Add testing guide

---

## PART E: SUCCESS CRITERIA

Feature #2 is DONE when:

✅ **User can see dashboard:**
1. Summary stats load and display
2. Booking history loads and displays
3. Payment history shows correctly
4. User profile displays correctly

✅ **User can interact:**
1. Filter bookings by status
2. Sort bookings by date/amount
3. Paginate through results
4. View booking details
5. Edit profile information
6. Save frequently-used routes

✅ **Data integrity:**
- Dashboard data matches database
- Filters work correctly
- Pagination works correctly
- Sorting works correctly
- No data duplication

✅ **All tests passing:**
- Unit tests for API
- Integration tests for flow
- Component tests for rendering

---

## PART F: DEPENDENCY MAP

```
Feature #2 (User Dashboard)
    ↓ (depends on)
Feature #1 (Booking & Payment) ✅ COMPLETE
    ├── Booking table data ✓
    ├── Payment records ✓
    └── User authentication ✓

Feature #2 (enables)
    ↓
Feature #3 (Email Notifications) - Needs booking/payment events
    ↓
Feature #4 (Telegram Bot) - Needs booking data
    ↓
Feature #5 (Admin Dashboard) - Needs all booking data
```

---

## PART G: TIME ESTIMATE BREAKDOWN

| Task | Estimate | Notes |
|------|----------|-------|
| Fix endpoint paths | 15m | Simple string changes |
| Create API client | 30m | Straightforward fetch calls |
| Create hooks | 30m | Follow Feature #1 pattern |
| Wire components | 45m | Connect data to UI |
| Add filtering | 30m | Dropdown + API calls |
| Add pagination | 30m | Buttons + state mgmt |
| Saved routes | 30m | localStorage-based |
| Profile editing | 30m | Form + submit |
| Testing & debugging | 45m | E2E flow validation |
| Documentation | 15m | Commit messages, docs |
| **TOTAL** | **~4 hours** | **End-to-end** |

---

**Spec Ready for Implementation**  
**Next Step:** STEP 3 (Rapid Implementation)
