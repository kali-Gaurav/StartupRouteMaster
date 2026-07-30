# Feature #5: Route Search & Recommendation - Deep Analysis
## Specification & Implementation Planning

**Date**: 2026-07-29  
**Phase**: SPEC (Deep Analysis)  
**Status**: IN PROGRESS

---

## PART 1: REQUIREMENTS ANALYSIS

### 1.1 Feature Scope
Route Search & Recommendation system that:
1. Allows users to search trains by origin/destination/date/class
2. Returns ranked results with availability & pricing
3. Recommends alternatives based on user preferences & behavior
4. Tracks search events for analytics & ML training

### 1.2 User Stories

**US-1**: As a user, I want to search trains so I can find available options
- Input: origin, destination, date, class (optional)
- Output: Ranked list of trains with fare, duration, rating
- Performance: < 2 seconds
- Mobile-friendly response

**US-2**: As a regular user, I want personalized recommendations
- Input: User profile + recent searches
- Output: 5-10 tailored route suggestions
- Variety: Different times, fares, trains
- Relevance: Match user's historical preferences

**US-3**: As the system, I want to learn from search behavior
- Track: Search queries, results shown, clicks, conversions
- Use: Retrain models daily for better recommendations
- Monitor: Search accuracy, conversion rates, user satisfaction

### 1.3 Non-Functional Requirements

| Requirement | Target | Current | Gap |
|-------------|--------|---------|-----|
| Search latency | <2s | Unknown | TBD |
| Result freshness | Real-time | 5-min cache | -4:55 |
| Recommendation accuracy | >80% CTR | Baseline | TBD |
| Concurrent searches | 1000/sec | Unknown | TBD |
| Scalability | 10M users | Unknown | TBD |

---

## PART 2: DATA MODEL ANALYSIS

### 2.1 Models Already in Database

**Read-Only (Transit Data)**:
- TrainMaster: Train metadata
- Trip: Train trips/routes
- Segment: Trip segments
- Stop: Train stops
- Calendar: Operating calendar
- CalendarDate: Calendar dates

**Real-Time (Availability)**:
- TrainAvailabilityCache: Cached availability by class
- SeatInventory: Real-time seat status
- QuotaInventory: Quota availability
- Fare: Fare rules & pricing
- TrainLiveUpdate: Current running status

**User Data (for Recommendations)**:
- User: User profile
- UserTravelPreference: Preferred routes (learned)
- UserPreferenceModel: ML embeddings
- RouteKnowledge: Route characteristics (algorithm.py)
- StationKnowledge: Station characteristics (algorithm.py)

**Analytics**:
- RouteSearchLog: Search history
- SearchOutcome: Search results
- SearchEvent: Search analytics
- IntelligenceSearchEvent: AI intent classification
- RecommendationEvent: Recommendation tracking

### 2.2 Data Relationships

```
Search Workflow:
User Input (origin, dest, date, class)
    ↓
RouteSearchLog (record query)
    ↓
Query TrainMaster + Trip + Segment
    ↓
Check TrainAvailabilityCache + SeatInventory + Fare
    ↓
Generate SearchOutcome (per train)
    ↓
Rank results (relevance, price, rating)
    ↓
IntelligenceSearchEvent (intent analysis)
    ↓
Return to user

Recommendation Workflow:
User Profile (UserTravelPreference + UserPreferenceModel)
    ↓
Route Candidates (historical + trending + exploratory)
    ↓
Score each candidate:
  - User preference match: UserPreferenceModel
  - Availability: TrainAvailabilityCache
  - Price competitiveness: CompetitorPriceModel
  - Novelty: RouteKnowledge
    ↓
Diversify results (times, fares, trains)
    ↓
RecommendationEvent (track impressions)
    ↓
Return to user
```

---

## PART 3: SEARCH ALGORITHM DESIGN

### 3.1 Basic Search Flow

```python
class SearchAlgorithm:
    def search(self, origin, destination, date, class_type):
        # Step 1: Normalize inputs
        origin_code = resolve_station(origin)      # NDLS
        dest_code = resolve_station(destination)   # BCT
        travel_date = parse_date(date)             # 2026-08-15
        
        # Step 2: Query trains
        trips = db.query(Trip).filter(
            Trip.source_station == origin_code,
            Trip.destination_station == dest_code,
            # Check calendar for this date
        ).all()
        
        # Step 3: For each trip, check availability
        results = []
        for trip in trips:
            train = trip.train_master
            
            # Get cached availability
            cache = TrainAvailabilityCache.get(
                train_id=train.id,
                travel_date=travel_date,
                class_type=class_type
            )
            
            if cache.available_seats == 0:
                continue  # Skip fully booked
            
            # Get current fare
            fare = Fare.get(
                origin=origin_code,
                destination=dest_code,
                class_type=class_type,
                train_number=train.number
            )
            
            # Get live status
            live_update = TrainLiveUpdate.latest(train.number)
            
            # Create SearchOutcome
            outcome = SearchOutcome(
                search_id=uuid.uuid4(),
                train_number=train.number,
                departure_time=trip.departure_time,
                arrival_time=trip.arrival_time,
                duration_minutes=trip.duration_minutes,
                available_seats=cache.available_seats,
                fare=fare.final_fare,
                rating=train.avg_rating,
                delay_minutes=live_update.delay_minutes,
            )
            results.append(outcome)
        
        # Step 4: Rank results
        results = self.rank_results(results)
        
        # Step 5: Log search
        search_log = RouteSearchLog(
            user_id=current_user.id,
            origin=origin_code,
            destination=dest_code,
            travel_date=travel_date,
            class_type=class_type,
            filters={...},
            results_count=len(results),
        )
        db.add(search_log)
        
        return results
```

### 3.2 Ranking Algorithm

```python
def rank_results(self, results):
    """
    Rank search results by multiple criteria
    """
    scored_results = []
    
    for result in results:
        score = (
            0.3 * self.score_timing(result) +          # Prefer reasonable times
            0.25 * self.score_availability(result) +   # More seats = better
            0.25 * self.score_price(result) +          # Lower price better
            0.1 * self.score_reliability(result) +     # Delay history
            0.1 * self.score_comfort(result)           # Train ratings
        )
        
        scored_results.append((result, score))
    
    # Sort by score descending
    scored_results.sort(key=lambda x: x[1], reverse=True)
    
    # Return top 10-15 results
    return [r[0] for r in scored_results[:15]]

def score_timing(self, result):
    """Prefer convenient times: morning/evening"""
    hour = result.departure_time.hour
    if 6 <= hour <= 10:  # Morning
        return 1.0
    elif 16 <= hour <= 23:  # Evening
        return 0.9
    elif 11 <= hour <= 15:  # Afternoon
        return 0.7
    else:  # Night
        return 0.5

def score_availability(self, result):
    """More seats = better"""
    if result.available_seats == 0:
        return 0.0
    elif result.available_seats > 20:
        return 1.0
    else:
        return result.available_seats / 20.0

def score_price(self, result):
    """Normalize price to 0-1 (lower is better)"""
    min_fare, max_fare = self.get_fare_range()
    normalized = 1.0 - (result.fare - min_fare) / (max_fare - min_fare)
    return max(0, min(1, normalized))

def score_reliability(self, result):
    """Trains with less delay are better"""
    if result.delay_minutes < 5:
        return 1.0
    elif result.delay_minutes > 30:
        return 0.5
    else:
        return 1.0 - (result.delay_minutes / 60.0)

def score_comfort(self, result):
    """Train ratings 0-5 stars"""
    return min(1.0, result.rating / 5.0)
```

---

## PART 4: RECOMMENDATION ALGORITHM DESIGN

### 4.1 Recommendation Pipeline

```python
class RecommendationEngine:
    def get_recommendations(self, user_id, context=None):
        """Generate personalized recommendations"""
        
        # Load user profile
        user = db.get(User, user_id)
        user_pref = self.load_user_preference(user_id)
        behavior = self.load_user_behavior(user_id)
        
        # Get candidates
        candidates = self.generate_candidates(user_pref, behavior)
        
        # Score candidates
        scored = [(c, self.score_candidate(c, user_pref, behavior)) 
                  for c in candidates]
        
        # Sort and diversify
        recommendations = self.diversify(scored)
        
        # Track event
        rec_event = RecommendationEvent(
            user_id=user_id,
            recommendations=[r.id for r in recommendations],
            context=context,
        )
        db.add(rec_event)
        
        return recommendations
    
    def generate_candidates(self, user_pref, behavior):
        """Generate candidate routes"""
        candidates = []
        
        # 1. User's historical preferences (80% weight)
        if user_pref.preferred_routes:
            for route in user_pref.preferred_routes:
                candidates.append({
                    'type': 'historical',
                    'source': route['source'],
                    'dest': route['dest'],
                    'weight': 0.8,
                })
        
        # 2. Trending routes (10% weight)
        trending = self.get_trending_routes()
        for route in trending[:5]:
            candidates.append({
                'type': 'trending',
                'source': route.source_code,
                'dest': route.destination_code,
                'weight': 0.1,
            })
        
        # 3. Exploratory routes (5% weight)
        exploratory = self.get_exploratory_routes(user_pref)
        for route in exploratory[:3]:
            candidates.append({
                'type': 'exploratory',
                'source': route.source,
                'dest': route.dest,
                'weight': 0.05,
            })
        
        # 4. Similar users' favorites (5% weight)
        similar = self.get_similar_users(user_id)
        for user in similar[:2]:
            pref = self.load_user_preference(user.id)
            if pref.preferred_routes:
                candidates.append({
                    'type': 'collaborative',
                    'source': pref.preferred_routes[0]['source'],
                    'dest': pref.preferred_routes[0]['dest'],
                    'weight': 0.05,
                })
        
        return candidates
    
    def score_candidate(self, candidate, user_pref, behavior):
        """Score individual candidate"""
        source = candidate['source']
        dest = candidate['dest']
        
        score = (
            0.4 * self.preference_match(source, dest, user_pref) +
            0.3 * self.availability_score(source, dest) +
            0.2 * self.price_competitiveness(source, dest) +
            0.1 * self.novelty_factor(source, dest, behavior)
        )
        
        return score
    
    def preference_match(self, source, dest, user_pref):
        """How well does this route match user preferences?"""
        score = 0
        
        # Preferred departure times
        score += self.time_preference_score(user_pref)
        
        # Preferred class
        score += self.class_preference_score(user_pref)
        
        # Preferred trains
        if self.has_user_preference(source, dest, user_pref):
            score = 1.0
        
        return min(1.0, score)
    
    def diversify(self, scored_candidates):
        """Ensure variety in recommendations"""
        recommended = []
        seen_sources = set()
        seen_dests = set()
        
        # Sort by score
        scored_candidates.sort(key=lambda x: x[1], reverse=True)
        
        for candidate, score in scored_candidates:
            if len(recommended) >= 10:
                break
            
            # Avoid duplicates
            key = (candidate['source'], candidate['dest'])
            if key in [(r['source'], r['dest']) for r in recommended]:
                continue
            
            # Avoid too many from same source/dest
            if candidate['source'] in seen_sources and len([r for r in recommended if r['source'] == candidate['source']]) >= 2:
                continue
            if candidate['dest'] in seen_dests and len([r for r in recommended if r['dest'] == candidate['dest']]) >= 2:
                continue
            
            seen_sources.add(candidate['source'])
            seen_dests.add(candidate['dest'])
            recommended.append(candidate)
        
        return recommended
```

---

## PART 5: API ENDPOINTS REQUIRED

### 5.1 Search Endpoint

```
POST /api/v1/search
Content-Type: application/json

Request:
{
    "origin": "Mumbai Central",      # OR "BCNT" (code)
    "destination": "Delhi",           # OR "NDLS" (code)
    "travel_date": "2026-08-15",
    "class": "AC2",                   # Optional: SL, AC3, AC2, AC1
    "passengers": 2,                  # Optional, default 1
    "departure_after": "06:00",       # Optional
    "departure_before": "22:00",      # Optional
    "max_duration_hours": 36,         # Optional
}

Response (200 OK):
{
    "search_id": "uuid",
    "origin_code": "BCNT",
    "destination_code": "NDLS",
    "travel_date": "2026-08-15",
    "results_count": 12,
    "results": [
        {
            "search_outcome_id": "uuid",
            "train_number": "12345",
            "train_name": "Mumbai Express",
            "departure_time": "22:00",
            "arrival_time": "08:30",
            "duration_minutes": 630,
            "available_seats": 45,
            "fare": 3500,
            "rating": 4.5,
            "class": "AC2",
            "delay_minutes": 5,
            "occupancy_percent": 75,
        },
        ...
    ],
    "generated_at": "2026-07-29T10:30:00Z",
}

Errors:
- 400: Invalid origin/destination
- 400: Invalid date (past or >60 days)
- 400: No trains available
- 500: Search timeout
```

### 5.2 Recommendations Endpoint

```
GET /api/v1/recommendations
Authorization: Bearer token
Query Params:
  - context: optional context (e.g., "home", "app_launch")

Response (200 OK):
{
    "recommendations": [
        {
            "recommendation_id": "uuid",
            "origin": "NDLS",
            "destination": "BCT",
            "origin_name": "Delhi",
            "destination_name": "Mumbai",
            "reason": "You typically book this route on weekends",
            "type": "historical",
            "suggested_date": "2026-08-16",  # Next occurrence
            "suggested_class": "AC2",
            "estimated_fare_range": [3200, 4500],
            "confidence": 0.92,
        },
        ...
    ],
    "generated_at": "2026-07-29T10:35:00Z",
}
```

### 5.3 Search Analytics Endpoint (Internal)

```
GET /api/v1/admin/search-analytics
Query Params:
  - start_date: 2026-07-20
  - end_date: 2026-07-29
  - group_by: route | user | hour

Response:
{
    "period": {start_date, end_date},
    "total_searches": 125000,
    "searches_with_results": 118500,
    "zero_result_searches": 6500,
    "searches_to_booking_conversion": 0.18,  # 18% convert
    "avg_results_shown": 12.3,
    "click_through_rate": 0.65,
    "top_routes": [
        {"source": "NDLS", "dest": "BCT", "search_count": 8500},
        ...
    ],
}
```

---

## PART 6: IMPLEMENTATION TASKS

### Task Breakdown

| Task | File | LOC | Effort | Priority |
|------|------|-----|--------|----------|
| Search API endpoint | api/v1/search.py | 100 | 2h | P0 |
| Search algorithm | services/search_service.py | 300 | 4h | P0 |
| Recommendation engine | services/recommendation_service.py | 250 | 3h | P0 |
| Recommendation API | api/v1/recommendations.py | 80 | 1h | P1 |
| Analytics tracking | api/v1/analytics/search.py | 150 | 2h | P1 |
| Unit tests | tests/test_search_service.py | 200 | 3h | P0 |
| Manual test guide | tests/SEARCH_MANUAL_TESTS.md | 400 | 2h | P1 |
| Integration tests | tests/test_search_integration.py | 150 | 2h | P1 |

**Total**: ~1,600 LOC, ~19 hours estimated

### Task Dependencies

```
1. Search API + Algorithm (parallel)
   ├─ Depends on: DB models (exist), Fare service
   └─ Blocking: Tests, Integration
   
2. Recommendation Engine (parallel)
   ├─ Depends on: User Preference models
   └─ Blocking: Recommendation API, Tests
   
3. Unit Tests
   ├─ Depends on: Services
   └─ Blocking: Integration tests
   
4. Integration Tests
   ├─ Depends on: Unit tests, APIs
   └─ Blocking: Manual testing
   
5. Manual Tests + Analytics
   ├─ Depends on: All above
   └─ Documentation only
```

---

## PART 7: KNOWN CHALLENGES & MITIGATIONS

| Challenge | Impact | Mitigation |
|-----------|--------|-----------|
| Real-time availability staleness | Incorrect seat counts shown | Cache refresh every 5 min, show cache timestamp |
| Performance under load | >2s search latency | Query optimization, Redis caching, pagination |
| Cold start for new users | No preference data | Use trending routes + exploratory recommendations |
| Recommendation quality | Low CTR | A/B test ranking weights, monitor CTR, retrain daily |
| Station name resolution | User input ambiguity | Fuzzy matching (Levenshtein distance), autocomplete |
| Cross-route recommendations | "Did you mean?" | Track search failures, offer corrections |

---

## PART 8: SUCCESS CRITERIA

### Functional
- ✓ Search returns results in <2 seconds
- ✓ Results include all required fields (fare, availability, timing)
- ✓ Ranking considers fare, availability, timing, rating
- ✓ Recommendations personalized by user preference
- ✓ Search events logged for analytics
- ✓ Recommendation impressions tracked

### Non-Functional
- ✓ Search results cached for 5 minutes
- ✓ Concurrent searches 100+/sec
- ✓ Recommendation generation <500ms
- ✓ Unit test coverage >80%
- ✓ Manual tests all passing

### User Experience
- ✓ Results ranked by relevance
- ✓ Diverse recommendations (different times/prices)
- ✓ Mobile-friendly response format
- ✓ Clear availability messaging

---

## PART 9: IMPLEMENTATION STRATEGY

### Phase 1: Core Search (Day 1)
1. Create search service (SearchAlgorithm class)
2. Implement ranking algorithm
3. Create search API endpoint
4. Add unit tests

### Phase 2: Recommendations (Day 1-2)
1. Create recommendation service
2. Implement candidate generation
3. Implement scoring algorithm
4. Create recommendations API
5. Add unit tests

### Phase 3: Analytics & Tracking (Day 2)
1. Track search events
2. Track recommendation events
3. Track recommendation clicks/conversions
4. Create analytics dashboard endpoint

### Phase 4: Testing & Polish (Day 2-3)
1. Integration tests
2. Manual test execution
3. Performance optimization
4. Bug fixes from testing

### Phase 5: Documentation & Learning (Day 3)
1. Create manual test guide
2. Document algorithms
3. Document learnings & insights
4. Record metrics

---

## PART 10: SUCCESS METRICS

| Metric | Target | Success |
|--------|--------|---------|
| Search latency (p95) | <2s | ✓ |
| Search result accuracy | 95%+ relevant | TBD |
| Recommendation CTR | >60% | TBD |
| Recommendation conversion | >15% | TBD |
| Test coverage | >80% | TBD |
| Manual test pass rate | 100% | TBD |

---

**END OF ANALYSIS**

Ready to move to IMPLEMENTATION phase.
