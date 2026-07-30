# Code Quality & Polish Guide - RouteMaster V2

**Created:** July 29, 2026  
**Purpose:** Standardize code quality, refactor incomplete features, and polish existing implementations  
**Target:** Production-ready codebase

---

## PART 1: CODE QUALITY STANDARDS

### 1.1 BACKEND (Python/FastAPI) STANDARDS

#### Code Style
```python
# ✅ GOOD - PEP 8 compliant, clear, documented
@router.get("/api/v1/routes/search")
async def search_routes(
    from_station: str,
    to_station: str,
    date: datetime,
    db: Database = Depends(get_db)
) -> List[RouteResponse]:
    """
    Search for train routes between two stations.
    
    Args:
        from_station: Starting station code (e.g., 'NDLS')
        to_station: Destination station code (e.g., 'BCT')
        date: Journey date
        db: Database connection
    
    Returns:
        List of available routes with fares
    """
    routes = await db.query(Route).filter(
        Route.from_station == from_station,
        Route.to_station == to_station,
        Route.date == date
    ).all()
    
    return [RouteResponse.from_orm(r) for r in routes]

# ❌ WRONG - No docs, poor naming, inconsistent
@router.get("/search")
async def get_routes(fs: str, ts: str, d: str, db=Depends()):
    r = db.query(Route).filter(Route.fs==fs, Route.ts==ts).all()
    return r
```

#### Import Organization
```python
# ✅ CORRECT ORDER
# 1. Standard library
import asyncio
from datetime import datetime, timedelta
from typing import List, Optional

# 2. Third-party
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select, and_
import httpx

# 3. Local imports
from ...database import get_db
from ...models import Route, Booking
from ...schemas import RouteResponse
from ..auth import verify_token
```

#### Error Handling
```python
# ✅ GOOD - Specific errors, proper logging
@router.post("/bookings")
async def create_booking(data: BookingRequest, user_id: str = Depends(verify_token)):
    try:
        if not data.passenger_name:
            raise HTTPException(400, "Passenger name is required")
        
        booking = Booking(**data.dict(), user_id=user_id)
        db.add(booking)
        await db.commit()
        
    except IntegrityError as e:
        logger.error(f"Booking creation failed: {e}")
        raise HTTPException(400, "Booking data validation failed")
    
    except Exception as e:
        logger.error(f"Unexpected error in create_booking: {e}", exc_info=True)
        raise HTTPException(500, "Internal server error")
    
    return booking

# ❌ WRONG - Broad except, swallows errors
@router.post("/bookings")
async def create_booking(data: BookingRequest):
    try:
        booking = Booking(**data.dict())
        db.add(booking)
        db.commit()
    except:
        return {"error": "failed"}
```

#### Testing Requirements
```python
# File: backend/tests/test_routes_search.py

import pytest
from httpx import AsyncClient

@pytest.mark.asyncio
async def test_search_routes_success():
    """Test successful route search"""
    client = AsyncClient(app=app, base_url="http://test")
    
    response = await client.get(
        "/api/v1/routes/search",
        params={
            "from_station": "NDLS",
            "to_station": "BCT",
            "date": "2026-08-15"
        }
    )
    
    assert response.status_code == 200
    data = response.json()
    assert len(data) > 0
    assert "train_number" in data[0]

@pytest.mark.asyncio
async def test_search_routes_invalid_station():
    """Test search with invalid station"""
    client = AsyncClient(app=app, base_url="http://test")
    
    response = await client.get(
        "/api/v1/routes/search",
        params={
            "from_station": "INVALID",
            "to_station": "BCT",
            "date": "2026-08-15"
        }
    )
    
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_search_routes_caching():
    """Test that search results are cached"""
    client = AsyncClient(app=app, base_url="http://test")
    
    # First call
    response1 = await client.get(...)
    # Second call (should be cached)
    response2 = await client.get(...)
    
    assert response1.json() == response2.json()
```

---

### 1.2 FRONTEND (React/TypeScript) STANDARDS

#### Component Structure
```typescript
// ✅ GOOD - Well-organized, documented, typed
import { useState, useEffect } from "react";
import { RouteCard } from "@/components/RouteCard";
import { useRoutes } from "@/api/hooks/useRoutes";
import { LoadingState } from "@/components/skeletons/LoadingState";
import { ErrorState } from "@/components/shared/ErrorState";

interface RouteSearchProps {
  fromStation: string;
  toStation: string;
  date: Date;
  onSelectRoute?: (route: Route) => void;
}

/**
 * RouteSearch component - displays search results with filtering and sorting
 */
export function RouteSearch({
  fromStation,
  toStation,
  date,
  onSelectRoute,
}: RouteSearchProps) {
  const [sortBy, setSortBy] = useState<"price" | "time" | "rating">("price");
  const { routes, loading, error } = useRoutes(fromStation, toStation, date);

  if (loading) return <LoadingState count={5} />;
  if (error) return <ErrorState error={error} />;
  if (!routes.length) return <EmptyState />;

  const sortedRoutes = sortRoutes(routes, sortBy);

  return (
    <div className="space-y-4">
      <div className="flex gap-2">
        <SortButton value={sortBy} onChange={setSortBy} />
      </div>

      <div className="grid gap-4">
        {sortedRoutes.map((route) => (
          <RouteCard
            key={route.id}
            route={route}
            onClick={() => onSelectRoute?.(route)}
          />
        ))}
      </div>
    </div>
  );
}

// ❌ WRONG - No types, poor organization, inline logic
export function RouteSearch(props) {
  const [sort, setSort] = useState("price");
  const routes = useRoutes();
  
  const sorted = routes.sort((a, b) => 
    sort === "price" ? a.price - b.price : a.time - b.time
  );

  return <div>{sorted.map(r => <RouteCard key={r.id} route={r} />)}</div>;
}
```

#### Hook Patterns
```typescript
// ✅ GOOD - Handles loading/error, clean dependencies
export function useRoutes(fromStation: string, toStation: string, date: Date) {
  const [routes, setRoutes] = useState<Route[]>([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;
    
    async function fetchRoutes() {
      setLoading(true);
      try {
        const data = await searchRoutes(fromStation, toStation, date);
        if (isMounted) setRoutes(data);
      } catch (err) {
        if (isMounted) setError(err.message);
      } finally {
        if (isMounted) setLoading(false);
      }
    }

    fetchRoutes();

    return () => {
      isMounted = false; // Cleanup
    };
  }, [fromStation, toStation, date]);

  return { routes, loading, error };
}

// ❌ WRONG - No cleanup, missing dependencies, errors ignored
export function useRoutes(from, to, date) {
  const [routes, setRoutes] = useState([]);

  useEffect(() => {
    searchRoutes(from, to, date).then(setRoutes);
  }); // Missing dependency array!

  return routes;
}
```

#### Testing Components
```typescript
// File: frontend/src/components/__tests__/RouteCard.test.tsx

import { render, screen } from "@testing-library/react";
import userEvent from "@testing-library/user-event";
import { RouteCard } from "@/components/RouteCard";

describe("RouteCard", () => {
  const mockRoute = {
    id: "1",
    trainNumber: "12951",
    trainName: "Rajdhani Express",
    fromStation: "NDLS",
    toStation: "BCT",
    departureTime: "06:00",
    arrivalTime: "16:30",
    fare: 2500,
    availableSeats: 50,
  };

  it("renders train information correctly", () => {
    render(<RouteCard route={mockRoute} />);
    
    expect(screen.getByText("12951")).toBeInTheDocument();
    expect(screen.getByText("Rajdhani Express")).toBeInTheDocument();
    expect(screen.getByText("₹2500")).toBeInTheDocument();
  });

  it("calls onBook callback when button is clicked", async () => {
    const onBook = jest.fn();
    render(<RouteCard route={mockRoute} onBook={onBook} />);
    
    await userEvent.click(screen.getByRole("button", { name: /book/i }));
    
    expect(onBook).toHaveBeenCalledWith(mockRoute);
  });

  it("shows loading state when isLoading prop is true", () => {
    render(<RouteCard route={mockRoute} isLoading={true} />);
    
    expect(screen.getByRole("status")).toBeInTheDocument();
  });
});
```

---

## PART 2: REFACTORING INCOMPLETE FEATURES

### 2.1 Search API (backend/api/v1/search.py)

**Current State:** 60% complete, needs optimization  
**Issues:** Missing pagination, no sorting, inefficient queries

```python
# File: backend/api/v1/search.py - REFACTORED VERSION

from fastapi import APIRouter, Query, Depends
from sqlalchemy import select, and_, func
from datetime import datetime
from typing import Optional

router = APIRouter(prefix="/api/v1", tags=["search"])

class SearchFilters:
    def __init__(
        self,
        from_station: str,
        to_station: str,
        date: datetime,
        sort_by: str = "price",
        min_price: Optional[float] = None,
        max_price: Optional[float] = None,
        departure_from: Optional[str] = None,
        departure_to: Optional[str] = None,
        skip: int = 0,
        limit: int = 20
    ):
        self.from_station = from_station.upper()
        self.to_station = to_station.upper()
        self.date = date.date()
        self.sort_by = sort_by
        self.min_price = min_price
        self.max_price = max_price
        self.departure_from = departure_from
        self.departure_to = departure_to
        self.skip = skip
        self.limit = limit

@router.get("/search/routes")
async def search_routes(
    from_station: str = Query(..., min_length=3),
    to_station: str = Query(..., min_length=3),
    date: datetime = Query(...),
    sort_by: str = Query("price", enum=["price", "time", "rating"]),
    min_price: Optional[float] = Query(None, ge=0),
    max_price: Optional[float] = Query(None, ge=0),
    skip: int = Query(0, ge=0),
    limit: int = Query(20, le=100),
    db = Depends(get_db)
):
    """
    Search for trains between two stations.
    
    Query Parameters:
    - from_station: Departure station code (NDLS, BCT, etc)
    - to_station: Arrival station code
    - date: Journey date (ISO format)
    - sort_by: Sort results by price|time|rating
    - min_price, max_price: Price filter in rupees
    - skip, limit: Pagination
    
    Returns:
    - List of routes with fares and availability
    """
    
    filters = SearchFilters(
        from_station, to_station, date,
        sort_by, min_price, max_price,
        skip=skip, limit=limit
    )
    
    try:
        # Check cache first
        cache_key = f"search:{filters.from_station}:{filters.to_station}:{filters.date}"
        cached = await redis.get(cache_key)
        
        if cached:
            return json.loads(cached)
        
        # Query database with proper indexes
        query = select(Route).where(
            and_(
                Route.from_station == filters.from_station,
                Route.to_station == filters.to_station,
                Route.date == filters.date,
                Route.status == "ACTIVE"
            )
        )
        
        # Apply price filters if provided
        if filters.min_price is not None:
            query = query.where(Route.base_fare >= filters.min_price)
        if filters.max_price is not None:
            query = query.where(Route.base_fare <= filters.max_price)
        
        # Sort
        if filters.sort_by == "price":
            query = query.order_by(Route.base_fare.asc())
        elif filters.sort_by == "time":
            query = query.order_by(Route.duration.asc())
        elif filters.sort_by == "rating":
            query = query.order_by(Route.average_rating.desc())
        
        # Paginate
        query = query.offset(filters.skip).limit(filters.limit + 1)
        
        routes = await db.execute(query)
        results = routes.scalars().all()
        
        # Check if there are more results
        has_more = len(results) > filters.limit
        if has_more:
            results = results[:filters.limit]
        
        # Format response
        response = {
            "routes": [RouteResponse.from_orm(r) for r in results],
            "pagination": {
                "skip": filters.skip,
                "limit": filters.limit,
                "has_more": has_more
            },
            "filters_applied": {
                "sort_by": filters.sort_by,
                "price_min": filters.min_price,
                "price_max": filters.max_price
            }
        }
        
        # Cache for 1 hour
        await redis.setex(cache_key, 3600, json.dumps(response, default=str))
        
        return response
        
    except Exception as e:
        logger.error(f"Search error: {e}", exc_info=True)
        raise HTTPException(500, "Search failed")
```

### 2.2 Booking Flow (frontend/src/pages/Bookings.tsx)

**Current State:** 40% complete, payment modal incomplete  
**Issues:** Props mismatched, modal cut off, missing state management

Let me check the existing Bookings.tsx file and refactor it:

---

## PART 3: MIGRATION & DEPLOYMENT CHECKLIST

### 3.1 Database Migration Checklist

```bash
# 1. Create migration for new tables
alembic revision --autogenerate -m "add user_profiles and saved_routes tables"

# 2. Review migration
cat alembic/versions/XXXX_add_user_profiles.py

# 3. Test migration locally
alembic upgrade head

# 4. Verify tables created
psql -c "SELECT * FROM user_profiles LIMIT 1"

# 5. Add rollback test
alembic downgrade -1
alembic upgrade head

# 6. Create indexes
CREATE INDEX idx_saved_routes_user_id ON saved_routes(user_id);
CREATE INDEX idx_payment_methods_user_id ON payment_methods(user_id);

# 7. Verify performance
EXPLAIN ANALYZE SELECT * FROM saved_routes WHERE user_id = '...';
```

### 3.2 Environment Variables Checklist

```bash
# .env.example - Add these new variables

# SendGrid
SENDGRID_API_KEY=your_api_key_here
SENDGRID_FROM_EMAIL=noreply@routemaster.app

# Twilio
TWILIO_ACCOUNT_SID=your_account_sid
TWILIO_AUTH_TOKEN=your_auth_token
TWILIO_FROM_NUMBER=+1234567890

# Telegram Bot
TELEGRAM_BOT_TOKEN=your_bot_token
TELEGRAM_BOT_USERNAME=yourbot

# Redis
REDIS_URL=redis://localhost:6379/0

# Admin features
ADMIN_SECRET_KEY=your_admin_key

# Razorpay
RAZORPAY_KEY_ID=your_key_id
RAZORPAY_KEY_SECRET=your_key_secret
RAZORPAY_WEBHOOK_SECRET=your_webhook_secret
```

### 3.3 Frontend Build Checklist

```bash
# 1. Check for TypeScript errors
npm run type-check

# 2. Lint code
npm run lint

# 3. Test build
npm run build

# 4. Check bundle size
npm run build -- --analyze

# 5. Test in production mode
npm run preview

# 6. Lighthouse audit
npm run lighthouse

# 7. Accessibility check
npm run a11y
```

### 3.4 Backend Testing Checklist

```bash
# 1. Run unit tests
pytest backend/tests/unit -v

# 2. Run integration tests
pytest backend/tests/integration -v

# 3. Run API tests
pytest backend/tests/api -v --tb=short

# 4. Coverage report
pytest --cov=backend --cov-report=html

# 5. Security scan
bandit -r backend/

# 6. Dependency audit
pip-audit
```

---

## PART 4: POLISH CHECKLIST

### 4.1 Frontend Polish

- [ ] **Performance**
  - [ ] Core Web Vitals > 80 (Lighthouse)
  - [ ] FCP < 1.5s
  - [ ] LCP < 2.5s
  - [ ] CLS < 0.1
  - [ ] TTI < 3.5s

- [ ] **Responsive Design**
  - [ ] Mobile (375px) ✓
  - [ ] Tablet (768px) ✓
  - [ ] Desktop (1920px) ✓
  - [ ] Touch targets min 48px ✓

- [ ] **Accessibility (A11y)**
  - [ ] WCAG 2.1 AA compliant
  - [ ] Keyboard navigation works
  - [ ] Screen reader compatible
  - [ ] Color contrast > 4.5:1
  - [ ] No focus traps

- [ ] **Error States**
  - [ ] 404 page designed
  - [ ] 500 error page designed
  - [ ] Network error handling
  - [ ] Form validation messages
  - [ ] API error messages clear

- [ ] **Loading States**
  - [ ] Skeleton screens created
  - [ ] Loading spinners styled
  - [ ] Lazy loading implemented
  - [ ] No layout shift during load

- [ ] **User Feedback**
  - [ ] Toast notifications
  - [ ] Confirmations for destructive actions
  - [ ] Success messages clear
  - [ ] Error messages helpful

### 4.2 Backend Polish

- [ ] **API Documentation**
  - [ ] Swagger/OpenAPI docs complete
  - [ ] All endpoints documented
  - [ ] Request/response examples provided
  - [ ] Error codes documented

- [ ] **Logging**
  - [ ] All API calls logged
  - [ ] Error logging with context
  - [ ] Structured logging (JSON)
  - [ ] Log rotation configured

- [ ] **Monitoring**
  - [ ] Error tracking (Sentry)
  - [ ] Performance monitoring
  - [ ] Uptime monitoring
  - [ ] Alert thresholds set

- [ ] **Rate Limiting**
  - [ ] Implemented on all endpoints
  - [ ] Per-user limits set
  - [ ] IP-based limits for unauthenticated
  - [ ] Graceful 429 responses

- [ ] **Security**
  - [ ] CORS configured correctly
  - [ ] CSRF protection enabled
  - [ ] Input validation on all endpoints
  - [ ] SQL injection prevention
  - [ ] XSS prevention
  - [ ] Authentication required for private endpoints

### 4.3 Database Polish

- [ ] **Indexes**
  - [ ] Created for foreign keys
  - [ ] Created for frequently searched columns
  - [ ] Verified with EXPLAIN ANALYZE

- [ ] **Data Integrity**
  - [ ] Foreign key constraints added
  - [ ] NOT NULL constraints proper
  - [ ] Unique constraints applied
  - [ ] Check constraints for enums

- [ ] **Performance**
  - [ ] No N+1 queries
  - [ ] Pagination implemented
  - [ ] Caching strategy defined
  - [ ] Query timeouts set

- [ ] **Backup & Recovery**
  - [ ] Daily backups enabled
  - [ ] Backup restoration tested
  - [ ] Point-in-time recovery available
  - [ ] Disaster recovery documented

---

## PART 5: DEPLOYMENT STRATEGY

### 5.1 Staging Deployment

```bash
# 1. Push to staging branch
git push origin feature/xyz staging

# 2. Run automated tests on staging
# (CI/CD pipeline runs tests)

# 3. Deploy to staging environment
# (Automated via GitHub Actions)

# 4. Run smoke tests
pytest e2e/smoke_tests.py --env=staging

# 5. Performance benchmarks
pytest e2e/performance_tests.py --env=staging

# 6. Security scan
bandit -r backend/

# 7. Manual QA testing
# - Test on mobile
# - Test payment flow
# - Test error scenarios
```

### 5.2 Production Deployment

```bash
# 1. Create release PR
# - Bump version in package.json, pyproject.toml
# - Update CHANGELOG.md
# - Add release notes

# 2. Merge to main
git merge feature/xyz

# 3. Tag release
git tag -a v1.0.0 -m "Release v1.0.0"
git push origin v1.0.0

# 4. Automated production deployment
# (GitHub Actions / deployment pipeline)

# 5. Post-deployment checks
# - Verify uptime monitoring
# - Check error tracking
# - Monitor performance
# - User acceptance testing

# 6. Rollback procedure (if needed)
# - Revert to previous tag
# - Run migrations rollback
# - Notify users
```

---

## PART 6: CODE REVIEW CHECKLIST

### Before Submitting PR:

- [ ] **Code Quality**
  - [ ] No console.logs or debug statements
  - [ ] No TODO comments without ticket
  - [ ] PEP 8 compliant (Python)
  - [ ] Proper naming conventions
  - [ ] No hardcoded secrets/keys

- [ ] **Testing**
  - [ ] Unit tests added for new functions
  - [ ] Integration tests for new features
  - [ ] All tests passing locally
  - [ ] Coverage maintained/improved

- [ ] **Documentation**
  - [ ] Docstrings added to functions
  - [ ] README updated if needed
  - [ ] API docs updated
  - [ ] Changelog updated

- [ ] **Backwards Compatibility**
  - [ ] Breaking changes documented
  - [ ] Database migrations are reversible
  - [ ] API version bumped if breaking

- [ ] **Performance**
  - [ ] No new N+1 queries
  - [ ] Bundle size checked (frontend)
  - [ ] No unnecessary re-renders (React)
  - [ ] Caching strategy documented

- [ ] **Security**
  - [ ] No SQL injection risks
  - [ ] No XSS vulnerabilities
  - [ ] Proper auth/permission checks
  - [ ] Dependencies audited

---

## PART 7: CONTINUOUS IMPROVEMENT

### Weekly Review:
1. Review error logs
2. Analyze performance metrics
3. Check user feedback
4. Plan optimizations

### Monthly Review:
1. Security audit
2. Dependency updates
3. Performance benchmarks
4. User behavior analysis

---

**Last Updated:** July 29, 2026  
**Maintained By:** Engineering Team
