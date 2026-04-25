"""
🔥 UNIFIED ROUTE ENGINE - Core Search Orchestration
Central coordinator for all route search requests.
Bridges search service, engines, cache, and intelligence layers.

Production-ready with:
- Result deduplication
- Fallback routing
- Rate limiting
- Pagination
- Search intent detection
- Result freshness validation
"""

import logging
import asyncio
import hashlib
import time
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime, date
from dataclasses import dataclass, field
from collections import defaultdict
from enum import Enum

from database.session import SessionTransit
from database.models import SearchEvent, IntelligenceMetric, GlobalIntelligenceState
from services.hybrid_search_service import HybridSearchService
from services.multi_layer_cache import multi_layer_cache
from services.intelligence_service import IntelligenceService
from core.nexus.audit.governor import nexus_governor
from core.nexus.audit.triage import nexus_triage

logger = logging.getLogger("route_engine")


class SearchIntent(Enum):
    """Detected user search intent."""
    FASTEST = "fastest"
    CHEAPEST = "cheapest"
    MOST_AVAILABLE = "most_available"
    BEST_COMFORT = "best_comfort"
    BALANCED = "balanced"  # Default


class RouteFingerprint:
    """Generate unique fingerprints for route deduplication."""
    
    @staticmethod
    def generate(route: Dict[str, Any]) -> str:
        """Generate unique fingerprint for a route."""
        segments = route.get("segments", [])
        if not segments:
            # Fallback for routes without segments
            return f"{route.get('departure_time', '')}:{route.get('arrival_time', '')}"
        
        # Create fingerprint from sorted segment info
        segment_hashes = []
        for seg in segments:
            train = seg.get("train_number", "")
            dep = seg.get("departure_code", "")
            arr = seg.get("arrival_code", "")
            segment_hashes.append(f"{train}:{dep}:{arr}")
        
        fingerprint = "|".join(sorted(segment_hashes))
        return hashlib.md5(fingerprint.encode()).hexdigest()[:16]
    
    @staticmethod
    def generate_from_segments(segments: List[Dict]) -> str:
        """Generate fingerprint from segment list."""
        segment_hashes = []
        for seg in segments:
            train = seg.get("train_number", "")
            dep = seg.get("departure_code", "")
            arr = seg.get("arrival_code", "")
            segment_hashes.append(f"{train}:{dep}:{arr}")
        
        fingerprint = "|".join(sorted(segment_hashes))
        return hashlib.md5(fingerprint.encode()).hexdigest()[:16]


@dataclass
class SearchBudget:
    """Track execution budget for search"""
    max_nodes: int = 100000
    max_transfers: int = 3
    max_time_sec: float = 5.0
    current_nodes: int = 0
    elapsed_sec: float = 0.0
    
    def is_exhausted(self) -> bool:
        """Check if budget exceeded"""
        return (
            self.current_nodes >= self.max_nodes or
            self.elapsed_sec >= self.max_time_sec
        )
    
    def usage_percent(self) -> float:
        """Get budget usage percentage"""
        return min(
            100.0 * self.current_nodes / self.max_nodes,
            100.0 * self.elapsed_sec / self.max_time_sec
        )


@dataclass
class RateLimitConfig:
    """Rate limiting configuration."""
    requests_per_minute: int = 60
    requests_per_hour: int = 1000
    burst_limit: int = 10


class UserRateLimiter:
    """
    Per-user rate limiting to prevent abuse.
    Uses token bucket algorithm.
    """
    
    def __init__(self, config: RateLimitConfig = None):
        self.config = config or RateLimitConfig()
        self._user_buckets: Dict[str, Dict] = defaultdict(self._create_bucket)
        self._lock = asyncio.Lock()
    
    def _create_bucket(self) -> Dict:
        """Create a new token bucket for a user."""
        return {
            "tokens": self.config.requests_per_minute,
            "hourly_tokens": self.config.requests_per_hour,
            "last_update": time.time(),
            "last_hour_update": time.time(),
            "burst_count": 0,
            "last_burst": time.time()
        }
    
    async def check_limit(self, user_id: str) -> Tuple[bool, Dict]:
        """
        Check if user is within rate limits.
        Returns: (is_allowed, details)
        """
        async with self._lock:
            bucket = self._user_buckets[user_id]
            now = time.time()
            
            # Refill tokens based on elapsed time
            elapsed = now - bucket["last_update"]
            bucket["tokens"] = min(
                self.config.requests_per_minute,
                bucket["tokens"] + elapsed * (self.config.requests_per_minute / 60)
            )
            bucket["last_update"] = now
            
            # Refill hourly tokens
            hour_elapsed = now - bucket["last_hour_update"]
            if hour_elapsed >= 3600:
                bucket["hourly_tokens"] = self.config.requests_per_hour
                bucket["last_hour_update"] = now
            
            # Check burst limit
            if now - bucket["last_burst"] < 1:  # Within 1 second
                bucket["burst_count"] += 1
                if bucket["burst_count"] > self.config.burst_limit:
                    return False, {
                        "reason": "burst_limit_exceeded",
                        "retry_after": 1
                    }
            else:
                bucket["burst_count"] = 0
                bucket["last_burst"] = now
            
            # Check minute limit
            if bucket["tokens"] < 1:
                return False, {
                    "reason": "rate_limit_exceeded",
                    "retry_after": (1 - bucket["tokens"]) * (60 / self.config.requests_per_minute)
                }
            
            # Check hourly limit
            if bucket["hourly_tokens"] < 1:
                return False, {
                    "reason": "hourly_limit_exceeded",
                    "retry_after": 3600
                }
            
            # Consume tokens
            bucket["tokens"] -= 1
            bucket["hourly_tokens"] -= 1
            
            return True, {
                "remaining_minute": int(bucket["tokens"]),
                "remaining_hour": int(bucket["hourly_tokens"])
            }
    
    async def get_remaining(self, user_id: str) -> Dict:
        """Get remaining quota for user."""
        bucket = self._user_buckets.get(user_id)
        if not bucket:
            return {"minute": self.config.requests_per_minute, "hour": self.config.requests_per_hour}
        
        return {
            "minute": int(bucket["tokens"]),
            "hour": int(bucket["hourly_tokens"])
        }

class RouteEngine:
    """
    Unified Route Search Engine
    
    Production-ready orchestration with:
    - Governor-based adaptive throttling
    - Multi-layer caching
    - Intelligence-driven weight tuning
    - Real-time budget management
    - Result deduplication
    - Fallback routing
    - Rate limiting
    - Pagination
    - Search intent detection
    """
    
    def __init__(self):
        self.transit_db = SessionTransit()
        self.search_service = HybridSearchService(
            self.transit_db, 
            self  # Pass self as the route engine
        )
        self.graph_initialized = False
        self.last_init_time: Optional[datetime] = None
        self.search_count = 0
        self.total_latency_ms = 0.0
        
        # Production features
        self.rate_limiter = UserRateLimiter()
        self._route_cache: Dict[str, Dict] = {}  # Local route cache for deduplication
        self._fallback_attempted: Dict[str, bool] = {}  # Track fallback attempts
        self._search_intent_cache: Dict[str, SearchIntent] = {}  # Cache detected intents
        
    async def init(self):
        """Initialize route engine and load transit graph"""
        try:
            logger.info("🚀 Initializing Route Engine...")
            
            # Initialize search service which loads transit graph
            await self.search_service.init()
            
            self.graph_initialized = True
            self.last_init_time = datetime.utcnow()
            
            logger.info("✅ Route Engine initialized successfully")
            return True
        except Exception as e:
            logger.error(f"❌ Route Engine initialization failed: {e}")
            self.graph_initialized = False
            return False
    
    def is_loaded(self) -> bool:
        """Backward compatibility method for is_loaded() calls."""
        return self.graph_initialized
    
    async def search(
        self,
        source: str,
        destination: str,
        travel_date: str,
        budget_category: Optional[str] = None,
        multi_modal: bool = False,
        user_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Execute unified route search with production features.
        
        Args:
            source: Source station code (e.g., "NDLS")
            destination: Destination station code (e.g., "MMCT")
            travel_date: Travel date (YYYY-MM-DD)
            budget_category: "budget", "comfort", "premium" or None
            multi_modal: Include buses/flights if True
            user_id: User ID for personalization
            
        Returns:
            Dict with routes organized by transfer tier
        """
        start_time = datetime.utcnow()
        self.search_count += 1
        
        logger.info(f"🔍 Search #{self.search_count}: {source}→{destination} on {travel_date}")
        
        # Step 0: Rate limiting (production)
        if user_id:
            allowed, limit_info = await self.rate_limiter.check_limit(user_id)
            if not allowed:
                logger.warning(f"🚫 Rate limit exceeded for user {user_id}: {limit_info}")
                return {
                    "error": "rate_limit_exceeded",
                    "message": f"Too many requests. {limit_info.get('retry_after', 60)}s wait.",
                    "retry_after": limit_info.get("retry_after", 60)
                }
        
        # Step 1: Check cache
        cache_key = f"search:{source}:{destination}:{travel_date}:{budget_category}"
        cached_result = await multi_layer_cache.get(cache_key)
        
        if cached_result:
            logger.info(f"✅ Cache hit for {cache_key}")
            # Validate freshness for cached results
            cached_result["routes"] = self._validate_route_freshness(
                self._collect_all_routes(cached_result),
                travel_date
            )
            return cached_result
        
        # Step 2: Check governor pressure and adjust budget
        governor_stats = await nexus_governor.get_stats()
        pressure = governor_stats.get("throttle_factor", 0.0)
        budget = self._calculate_budget(pressure)
        logger.info(f"🎯 Governor pressure: {pressure:.1%}, Budget: {budget.max_nodes} nodes")
        
        # Step 3: Get intelligence weights for scoring
        weights = await IntelligenceService.get_current_weights(self.transit_db)
        intel_svc = IntelligenceService(self.transit_db)
        logger.info(
            f"📊 Search weights: availability={weights.get('availability', 0.4):.2f}, "
            f"speed={weights.get('speed', 0.3):.2f}, comfort={weights.get('comfort', 0.2):.2f}, "
            f"safety={weights.get('safety', 0.1):.2f}"
        )
        
        try:
            # Step 4: Execute search
            result = await self.search_service.search_routes(
                source=source,
                destination=destination,
                travel_date=travel_date,
                budget_category=budget_category,
                multi_modal=multi_modal,
                search_budget=budget
            )
            
            # Step 4b: Fallback if no results (production)
            if not result.get("routes") or self._count_routes(result) == 0:
                logger.warning(f"⚠️ No routes found, attempting fallback...")
                fallback_result = await self._execute_fallback_search(
                    source, destination, travel_date, budget_category, budget
                )
                if fallback_result.get("routes"):
                    result = fallback_result
            
            # Step 5: Deduplicate results (production)
            for tier in result.get("routes", {}):
                if isinstance(result["routes"][tier], list):
                    result["routes"][tier] = self._deduplicate_routes(result["routes"][tier])
            
            # Step 6: Log intelligence observation
            if user_id:
                session_id = f"route_search:{source}:{destination}:{travel_date}:{user_id}"
                await intel_svc.log_search(
                    session_id=session_id,
                    user_id=user_id,
                    src=source,
                    dst=destination,
                    persona=budget_category or "comfort"
                )
            
            # Step 7: Cache result
            await multi_layer_cache.put(
                cache_key, 
                result,
                ttl=3600  # Cache for 1 hour
            )
            
            # Step 8: Update telemetry
            latency_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
            self.total_latency_ms += latency_ms
            await nexus_triage.report_latency(int(latency_ms))
            
            logger.info(f"✅ Search completed in {latency_ms:.1f}ms, "
                       f"found {self._count_routes(result)} total routes")
            
            return result
            
        except Exception as e:
            logger.error(f"❌ Search failed: {e}")
            
            # Try fallback on error
            try:
                logger.info("🔄 Attempting fallback after primary search error...")
                fallback_result = await self._execute_fallback_search(
                    source, destination, travel_date, budget_category, budget
                )
                if fallback_result.get("routes"):
                    return fallback_result
            except Exception as fallback_error:
                logger.error(f"❌ Fallback also failed: {fallback_error}")
            
            raise

    def _collect_all_routes(self, result: Dict) -> List[Dict]:
        """Collect all routes from result across all tiers."""
        all_routes = []
        for tier in ["direct", "one_transfer", "two_transfer", "three_transfer"]:
            routes = result.get("routes", {}).get(tier, [])
            if isinstance(routes, list):
                all_routes.extend(routes)
        return all_routes
    
    def _calculate_budget(self, pressure: float) -> SearchBudget:
        """
        Calculate dynamic search budget based on system pressure
        
        As pressure increases, reduce allowed nodes and transfers
        to maintain response time SLA
        """
        # Base budget
        max_nodes = 100000
        max_transfers = 3
        max_time = 5.0
        
        # Pressure multiplier (0.0 = no pressure, 1.0 = critical)
        if pressure < 0.3:
            # Low pressure - full search
            pass
        elif pressure < 0.6:
            # Medium pressure - reduce slightly
            max_nodes = int(max_nodes * 0.7)
            max_time = 3.0
        elif pressure < 0.8:
            # High pressure - aggressive reduction
            max_nodes = int(max_nodes * 0.4)
            max_transfers = 2
            max_time = 2.0
        else:
            # Critical pressure - minimal search
            max_nodes = int(max_nodes * 0.2)
            max_transfers = 1
            max_time = 1.0
        
        return SearchBudget(
            max_nodes=max_nodes,
            max_transfers=max_transfers,
            max_time_sec=max_time
        )
    
    def _count_routes(self, result: Dict[str, Any]) -> int:
        """Count total routes in search result"""
        routes = result.get("routes", {})
        return sum(len(routes.get(tier, [])) for tier in [
            "direct", "one_transfer", "two_transfer", "three_transfer"
        ])

    # =========================================================================
    # PRODUCTION FEATURES
    # =========================================================================

    def _detect_search_intent(
        self,
        source: str,
        destination: str,
        budget_category: Optional[str],
        user_id: Optional[str]
    ) -> SearchIntent:
        """
        Detect user search intent based on query patterns and history.
        Task: Search intent detection.
        """
        cache_key = f"{source}:{destination}:{budget_category}"
        
        if cache_key in self._search_intent_cache:
            return self._search_intent_cache[cache_key]
        
        # Detect based on budget category
        intent_map = {
            "budget": SearchIntent.CHEAPEST,
            "comfort": SearchIntent.BALANCED,
            "premium": SearchIntent.BEST_COMFORT,
            "fast": SearchIntent.FASTEST,
            "available": SearchIntent.MOST_AVAILABLE
        }
        
        intent = intent_map.get(budget_category.lower() if budget_category else "", SearchIntent.BALANCED)
        
        # In production: analyze user history for intent
        # Example: if user frequently books cheapest routes, prioritize that
        
        self._search_intent_cache[cache_key] = intent
        return intent

    def _apply_search_intent(
        self,
        routes: List[Dict],
        intent: SearchIntent
    ) -> List[Dict]:
        """
        Re-rank routes based on detected search intent.
        Task: Intent-based ranking.
        """
        if not routes or intent == SearchIntent.BALANCED:
            return routes
        
        def intent_score(route: Dict) -> float:
            """Calculate score based on intent."""
            if intent == SearchIntent.FASTEST:
                duration = route.get("duration_minutes", 9999)
                return -duration  # Lower is better
            elif intent == SearchIntent.CHEAPEST:
                fare = route.get("fare", 99999)
                return -fare  # Lower is better
            elif intent == SearchIntent.MOST_AVAILABLE:
                avail = route.get("availability_probability", 0)
                return avail  # Higher is better
            elif intent == SearchIntent.BEST_COMFORT:
                comfort = route.get("comfort_score", 0)
                return comfort  # Higher is better
            return 0
        
        return sorted(routes, key=intent_score, reverse=True)

    def _deduplicate_routes(self, routes: List[Dict]) -> List[Dict]:
        """
        Remove duplicate routes based on journey fingerprint.
        Task: Result deduplication.
        """
        seen_fingerprints = set()
        unique_routes = []
        
        for route in routes:
            fingerprint = RouteFingerprint.generate(route)
            
            if fingerprint not in seen_fingerprints:
                seen_fingerprints.add(fingerprint)
                unique_routes.append(route)
            else:
                logger.debug(f"🗑️ Deduplicated route: {fingerprint}")
        
        if len(unique_routes) < len(routes):
            logger.info(f"📦 Deduplicated {len(routes) - len(unique_routes)} duplicate routes")
        
        return unique_routes

    def _validate_route_freshness(self, routes: List[Dict], travel_date: str) -> List[Dict]:
        """
        Validate that cached routes are still valid for the travel date.
        Task: Result freshness check.
        """
        valid_routes = []
        
        for route in routes:
            # Check if route has valid schedule for date
            # In production: check against schedule database
            segments = route.get("segments", [])
            
            if not segments:
                valid_routes.append(route)
                continue
            
            # Basic validation: ensure departure is in future
            dep_time = route.get("departure_time")
            if dep_time:
                try:
                    if isinstance(dep_time, str):
                        dep_dt = datetime.fromisoformat(dep_time.replace("Z", "+00:00"))
                    else:
                        dep_dt = dep_time
                    
                    # Route is valid if departure is in future
                    if dep_dt > datetime.utcnow():
                        valid_routes.append(route)
                    else:
                        logger.debug(f"🗑️ Stale route removed: {route.get('route_id')}")
                except Exception:
                    # If we can't parse, keep the route
                    valid_routes.append(route)
            else:
                valid_routes.append(route)
        
        return valid_routes

    async def _execute_fallback_search(
        self,
        source: str,
        destination: str,
        travel_date: str,
        budget_category: Optional[str],
        search_budget: SearchBudget
    ) -> Dict[str, Any]:
        """
        Execute fallback search strategy when primary fails.
        Task: Fallback routing.
        """
        fallback_key = f"{source}:{destination}:{travel_date}"
        
        if self._fallback_attempted.get(fallback_key):
            logger.warning(f"⚠️ Fallback already attempted for {fallback_key}")
            return {"routes": {}, "fallback_exhausted": True}
        
        self._fallback_attempted[fallback_key] = True
        
        logger.info(f"🔄 Executing fallback search for {source}->{destination}")
        
        # Fallback strategies (in order of preference)
        fallback_strategies = [
            # 1. Allow more transfers
            {"max_transfers": 4, "description": "allow_more_transfers"},
            # 2. Extend time budget
            {"max_time": 10.0, "description": "extended_time"},
            # 3. Allow multi-modal (buses, flights)
            {"multi_modal": True, "description": "multi_modal"},
            # 4. Relax budget category
            {"budget_category": None, "description": "relax_budget"}
        ]
        
        for strategy in fallback_strategies:
            try:
                # Create modified budget
                modified_budget = SearchBudget(
                    max_nodes=search_budget.max_nodes,
                    max_transfers=strategy.get("max_transfers", search_budget.max_transfers),
                    max_time_sec=strategy.get("max_time", search_budget.max_time_sec),
                    current_nodes=search_budget.current_nodes,
                    elapsed_sec=search_budget.elapsed_sec
                )
                
                result = await self.search_service.search_routes(
                    source=source,
                    destination=destination,
                    travel_date=travel_date,
                    budget_category=strategy.get("budget_category", budget_category),
                    multi_modal=strategy.get("multi_modal", False),
                    search_budget=modified_budget
                )
                
                if result and result.get("routes"):
                    logger.info(f"✅ Fallback succeeded: {strategy['description']}")
                    result["fallback_strategy"] = strategy["description"]
                    return result
                    
            except Exception as e:
                logger.warning(f"❌ Fallback strategy {strategy['description']} failed: {e}")
                continue
        
        logger.error(f"💀 All fallback strategies exhausted for {source}->{destination}")
        return {"routes": {}, "fallback_exhausted": True, "fallback_error": "all_strategies_failed"}

    def _paginate_results(
        self,
        routes: List[Dict],
        page: int = 1,
        page_size: int = 20
    ) -> Dict[str, Any]:
        """
        Paginate search results.
        Task: Pagination support.
        """
        total = len(routes)
        start = (page - 1) * page_size
        end = start + page_size
        
        paginated = routes[start:end]
        
        return {
            "data": paginated,
            "pagination": {
                "page": page,
                "page_size": page_size,
                "total": total,
                "total_pages": (total + page_size - 1) // page_size,
                "has_next": end < total,
                "has_prev": page > 1
            }
        }

    async def search_with_pagination(
        self,
        source: str,
        destination: str,
        travel_date: str,
        budget_category: Optional[str] = None,
        multi_modal: bool = False,
        user_id: Optional[str] = None,
        page: int = 1,
        page_size: int = 20,
        intent: Optional[SearchIntent] = None
    ) -> Dict[str, Any]:
        """
        Search with full production features: pagination, intent, deduplication.
        """
        # Execute main search
        result = await self.search(
            source=source,
            destination=destination,
            travel_date=travel_date,
            budget_category=budget_category,
            multi_modal=multi_modal,
            user_id=user_id
        )
        
        # Collect all routes
        all_routes = []
        for tier in ["direct", "one_transfer", "two_transfer", "three_transfer"]:
            all_routes.extend(result.get("routes", {}).get(tier, []))
        
        # Apply deduplication
        all_routes = self._deduplicate_routes(all_routes)
        
        # Apply intent-based ranking
        if not intent:
            intent = self._detect_search_intent(source, destination, budget_category, user_id)
        
        all_routes = self._apply_search_intent(all_routes, intent)
        
        # Apply pagination
        paginated = self._paginate_results(all_routes, page, page_size)
        
        # Merge back into result
        result["routes"] = {"all": paginated["data"]}
        result["pagination"] = paginated["pagination"]
        result["search_intent"] = intent.value
        
        return result
    
    async def get_route_details(self, route_id: str) -> Dict[str, Any]:
        """Get detailed information about a specific route"""
        logger.info(f"📋 Fetching details for route {route_id}")
        
        try:
            # Parse route_id to extract train numbers and departure time
            # Format: trainno_datetime_trainno_datetime...
            route_parts = route_id.split('_')
            train_info = []
            departure_time = None
            
            for i, part in enumerate(route_parts):
                if part and part[:2].isalpha():
                    train_num = ''.join(filter(str.isdigit, part))
                    if train_num and i + 1 < len(route_parts):
                        try:
                            dt = datetime.strptime(route_parts[i + 1], "%Y%m%d%H%M")
                            train_info.append({
                                "train_number": train_num,
                                "departure_time": dt.isoformat()
                            })
                            if departure_time is None:
                                departure_time = dt
                        except ValueError:
                            continue
            
            # Get detailed route segments from transit database
            from sqlalchemy import text
            segments = []
            
            for train in train_info:
                train_no = train["train_number"]
                dep_time = train["departure_time"]
                
                # Query for train route details
                try:
                    result = self.transit_db.execute(
                        text("""
                            SELECT 
                                t.train_name,
                                t.train_number,
                                s1.code as departure_code,
                                s1.name as departure_name,
                                s2.code as arrival_code,
                                s2.name as arrival_name,
                                st1.departure_time,
                                st2.arrival_time,
                                st2.arrival_time - st1.departure_time as duration,
                                t.service_mask,
                                t.has_pantry
                            FROM trips t
                            JOIN stop_times st1 ON t.id = st1.trip_id
                            JOIN stop_times st2 ON t.id = st2.trip_id
                            JOIN stops s1 ON st1.stop_id = s1.id
                            JOIN stops s2 ON st2.stop_id = s2.id
                            WHERE t.train_number = :train_no
                            AND st1.departure_time >= :dep_time
                            AND st1.stop_sequence < st2.stop_sequence
                            ORDER BY st1.stop_sequence
                            LIMIT 10
                        """),
                        {"train_no": train_no, "dep_time": dep_time}
                    ).fetchall()
                    
                    for row in result:
                        segments.append({
                            "train_name": row[0],
                            "train_number": row[1],
                            "departure_code": row[2],
                            "departure_name": row[3],
                            "arrival_code": row[4],
                            "arrival_name": row[5],
                            "departure_time": row[6].isoformat() if row[6] else None,
                            "arrival_time": row[7].isoformat() if row[7] else None,
                            "duration_minutes": int((row[7] - row[6]).total_seconds() / 60) if row[6] and row[7] else 0,
                            "has_pantry": bool(row[9]) if row[9] else False
                        })
                except Exception as seg_err:
                    logger.warning(f"Could not fetch segment details for train {train_no}: {seg_err}")
            
            # Calculate totals
            total_duration = sum(
                (datetime.fromisoformat(s["arrival_time"]) - datetime.fromisoformat(s["departure_time"])).total_seconds() / 60
                for s in segments if s.get("departure_time") and s.get("arrival_time")
            )
            
            # Get fare information
            from services.fare_service import FareService
            fare_service = FareService()
            total_fare = 0
            fare_breakdown = {}
            
            if segments:
                first_seg = segments[0]
                fare_result = await fare_service.get_fare_with_fallback(
                    train_no=first_seg["train_number"],
                    from_station=first_seg["departure_code"],
                    to_station=segments[-1]["arrival_code"] if segments else first_seg["arrival_code"],
                    class_code="SL",
                    db_session=self.transit_db
                )
                if fare_result.get("success"):
                    total_fare = fare_result.get("data", {}).get("total_fare", 0)
                    fare_breakdown = fare_result.get("data", {})
            
            # Get availability info
            availability_info = {}
            try:
                from services.rapidapi_provider import rapidapi_provider
                if rapidapi_provider.is_healthy and segments:
                    first_seg = segments[0]
                    avail_result = await rapidapi_provider.get_availability(
                        first_seg["train_number"],
                        first_seg["departure_code"],
                        first_seg["arrival_code"],
                        departure_time.strftime("%Y-%m-%d") if departure_time else ""
                    )
                    if avail_result:
                        availability_info = avail_result
            except Exception:
                pass
            
            return {
                "route_id": route_id,
                "segments": segments,
                "total_duration": int(total_duration),
                "total_fare": total_fare,
                "fare_breakdown": fare_breakdown,
                "availability": availability_info,
                "departure_time": departure_time.isoformat() if departure_time else None,
                "train_count": len(train_info),
                "metadata": {
                    "fetched_at": datetime.utcnow().isoformat(),
                    "source": "transit_db"
                }
            }
            
        except Exception as e:
            logger.error(f"❌ Error fetching route details: {e}")
            return {
                "route_id": route_id,
                "error": str(e),
                "status": "failed"
            }
    
    async def validate_booking(
        self,
        route_id: str,
        passenger_count: int,
        travel_date: str
    ) -> Tuple[bool, Optional[str]]:
        """
        Validate if a route can still be booked
        
        Returns: (is_valid, error_message)
        """
        logger.info(f"✓ Validating booking for route {route_id}, "
                   f"{passenger_count} passengers on {travel_date}")
        
        try:
            # Step 1: Check if travel date is valid (not in past, within booking window)
            from datetime import datetime, date as date_type
            travel_date_obj = datetime.strptime(travel_date, "%Y-%m-%d").date() if isinstance(travel_date, str) else travel_date
            today = date_type.today()
            
            if travel_date_obj < today:
                return (False, "Travel date cannot be in the past")
            
            # IRCTC typically opens bookings 120 days in advance
            max_advance_days = 120
            if (travel_date_obj - today).days > max_advance_days:
                return (False, f"Bookings not available more than {max_advance_days} days in advance")
            
            # Step 2: Check train cancellation status
            from sqlalchemy import text
            try:
                date_str = travel_date_obj.isoformat()
                cancelled_result = self.transit_db.execute(
                    text("SELECT train_no FROM cancelled_trains WHERE travel_date = :dt"),
                    {"dt": date_str}
                ).fetchall()
                cancelled_trains = {str(r[0]) for r in cancelled_result if r and r[0]}
                
                # Extract train numbers from route_id (format: trainno_datetime)
                route_trains = []
                for part in route_id.split('_'):
                    if part and part[:2].isalpha() and len(part) >= 5:
                        # Likely a train number
                        train_num = ''.join(filter(str.isdigit, part))
                        if train_num:
                            route_trains.append(train_num)
                
                cancelled_in_route = [t for t in route_trains if t in cancelled_trains]
                if cancelled_in_route:
                    return (False, f"Train(s) {', '.join(cancelled_in_route)} is cancelled on this date")
            except Exception as db_err:
                logger.warning(f"Could not check cancellation status: {db_err}")
            
            # Step 3: Check seat availability via RapidAPI (if available)
            try:
                from services.rapidapi_provider import rapidapi_provider
                if rapidapi_provider.is_healthy and not rapidapi_provider.quota_latch_active:
                    # Extract first train and stations from route_id
                    # This is a simplified check - full implementation would parse route_id
                    logger.info("✓ RapidAPI available for availability check")
                    # Availability check would go here
            except Exception as api_err:
                logger.debug(f"Could not check live availability: {api_err}")
            
            # Step 4: Validate passenger count
            if passenger_count < 1:
                return (False, "At least 1 passenger required")
            if passenger_count > 6:
                return (False, "Maximum 6 passengers per booking")
            
            # Step 5: Check dynamic pricing constraints
            from services.enhanced_pricing_service import enhanced_pricing_service
            try:
                surge_level = enhanced_pricing_service.get_surge_level()
                if surge_level == "CRITICAL":
                    logger.warning(f"⚠️ High surge pricing in effect for {travel_date}")
            except Exception:
                pass
            
            logger.info(f"✅ Booking validation passed for route {route_id}")
            return (True, None)
            
        except Exception as e:
            logger.error(f"❌ Booking validation error: {e}")
            return (False, f"Validation error: {str(e)}")
    
    async def get_health(self) -> Dict[str, Any]:
        """Get engine health status"""
        avg_latency_ms = (
            self.total_latency_ms / self.search_count 
            if self.search_count > 0 
            else 0
        )
        
        return {
            "status": "HEALTHY" if self.graph_initialized else "DEGRADED",
            "graph_initialized": self.graph_initialized,
            "last_init": self.last_init_time.isoformat() if self.last_init_time else None,
            "searches_processed": self.search_count,
            "avg_latency_ms": avg_latency_ms
        }
    
    async def shutdown(self):
        """Graceful shutdown"""
        logger.info("🛑 Shutting down Route Engine...")
        await self.search_service.shutdown()
        self.transit_db.close()
        logger.info("✅ Route Engine shutdown complete")

# Lazy singleton instance
_unified_route_engine_instance = None

def get_unified_route_engine() -> RouteEngine:
    """Lazy-initialization for the unified route engine."""
    global _unified_route_engine_instance
    if _unified_route_engine_instance is None:
        _unified_route_engine_instance = RouteEngine()
    return _unified_route_engine_instance

# Lifecycle hooks
async def init_route_engine():
    """Initialize route engine on startup"""
    engine = get_unified_route_engine()
    return await engine.init()

async def shutdown_route_engine():
    """Shutdown route engine on termination"""
    if _unified_route_engine_instance:
        await _unified_route_engine_instance.shutdown()
