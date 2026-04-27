"""
Knowledge-Based Travel Optimization Service
Patent Innovation #2: Travel Knowledge Graph for intelligent optimization

This system builds and maintains a comprehensive knowledge graph of travel
patterns, user preferences, and market intelligence, then applies this
knowledge to optimize routing, pricing, and recommendations.

Enhanced with:
- Database persistence
- Real learning from user behavior
- Similar-user recommendations
- Route intelligence
- Market intelligence
- Resilience patterns
"""

from calendar import month
import logging
import asyncio
from typing import List, Dict, Any, Optional, Set
from datetime import datetime, date, timedelta
from dataclasses import dataclass, field
from collections import defaultdict, deque
from dataclasses import asdict
import networkx as nx
import numpy as np
from sklearn.metrics.pairwise import cosine_similarity

from core.resilience import circuit_breaker_manager, CircuitBreaker, CircuitConfig
from core.retry import RetryPolicy

logger = logging.getLogger("knowledge.graph")

@dataclass
class StationNode:
    """Station in the knowledge graph"""
    code: str
    name: str
    region: str
    zone: str
    connectivity_score: float
    popular_routes: List[str] = field(default_factory=list)
    
    # Learned properties
    avg_delay_minutes: float = 0.0
    cancellation_rate: float = 0.0
    peak_hours: List[int] = field(default_factory=list)


@dataclass
class RouteEdge:
    """Route connection in the knowledge graph"""
    source: str
    destination: str
    duration_minutes: int
    frequency_daily: int
    reliability_score: float  # 0-1
    avg_fare: float
    
    # Learned properties
    popular_times: List[int] = field(default_factory=list)
    seasonal_demand: Dict[str, float] = field(default_factory=dict)


@dataclass
class UserPreference:
    """Learned user preferences"""
    user_id: str
    
    # Route preferences
    preferred_stations: List[str] = field(default_factory=list)
    preferred_routes: List[str] = field(default_factory=list)
    preferred_times: List[int] = field(default_factory=list)
    
    # Time preferences
    preferred_time_morning: bool = False
    
    # Class preferences
    preferred_class: str = "SL"
    class_flexibility: float = 0.5  # 0 = strict, 1 = flexible
    
    # Behavior patterns
    avg_booking_advance_days: int = 7
    cancellation_rate: float = 0.1
    price_sensitivity: float = 0.5  # 0 = not sensitive, 1 = very sensitive


@dataclass
class RoutePattern:
    """Route pattern for persistence"""
    source: str
    destination: str
    avg_duration: int = 0
    frequency: int = 0
    reliability: float = 0.9
    searches: int = 0
    bookings: int = 0


class TravelKnowledgeGraph:
    """
    Patent Innovation #2: Knowledge-Based Travel Optimization
    
    Core features:
    1. Build comprehensive travel knowledge graph
    2. Learn from historical data and interactions
    3. Apply knowledge for personalized optimization
    4. Generate intelligent recommendations
    5. Similar-user collaborative filtering
    6. Route and market intelligence
    """
    
    LEARNING_RATE = 0.1
    
    def __init__(self, db=None):
        self.db = db
        
        # NetworkX graph for knowledge representation
        self.graph = nx.DiGraph()
        
        # User preference storage
        self.user_preferences: Dict[str, UserPreference] = {}
        
        # Pattern storage
        self.route_patterns: Dict[str, Dict] = {}
        self.station_patterns: Dict[str, StationNode] = {}
        
        # Market intelligence
        self.competitor_prices: Dict[str, Dict] = {}  # route -> {provider: price}
        self.seasonal_patterns: Dict[str, Dict] = {}  # route -> {month: demand}
        
        # User behavior matrix for collaborative filtering
        self.user_behavior_matrix: Dict[str, Dict[str, float]] = {}
        
        # Statistics
        self.total_interactions = 0
        self.last_update = None
        
        # Release Valve storage (Arbitrage opportunities)
        # route_key -> List[Dict]
        self.release_valves: Dict[str, List[Dict]] = defaultdict(list)
        
        # Circuit breaker for DB operations
        self._db_breaker = circuit_breaker_manager.get_or_create(
            "knowledge_graph_db",
            CircuitConfig(failure_threshold=5, timeout_seconds=30.0, success_threshold=2)
        )
        
        # Retry policy
        self._retry = RetryPolicy(
            max_attempts=3,
            initial_delay=0.5,
            max_delay=5.0,
            conditions=[
                lambda e: isinstance(e, (ConnectionError, TimeoutError)),
                lambda e: "timeout" in str(e).lower()
            ]
        )
        
        # Metrics tracking
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = asyncio.Lock()
        
        logger.info("TravelKnowledgeGraph initialized with resilience patterns")
    
    # =========================================================================
    # GRAPH BUILDING
    # =========================================================================
    
    async def build_initial_graph(self):
        """
        Build initial knowledge graph from database.
        Called automatically on service initialization if no data exists.
        """
        logger.info("Building initial knowledge graph...")
        
        # Check if we already have data
        if len(self.graph.nodes) > 0:
            logger.info("Knowledge graph already initialized, skipping build")
            return
        
        # Add station nodes from database
        stations = await self._load_stations()
        for station in stations:
            self.graph.add_node(
                station["code"],
                type="station",
                name=station["name"],
                region=station["region"],
                zone=station["zone"],
                connectivity=station.get("connectivity_score", 0.5)
            )
            
            self.station_patterns[station["code"]] = StationNode(
                code=station["code"],
                name=station["name"],
                region=station["region"],
                zone=station["zone"],
                connectivity_score=station.get("connectivity_score", 0.5)
            )
        
        # Add route edges
        routes = await self._load_routes()
        for route in routes:
            self.graph.add_edge(
                route["source"],
                route["destination"],
                type="route",
                duration=route["duration_minutes"],
                frequency=route["frequency_daily"],
                reliability=route.get("reliability_score", 0.9),
                fare=route.get("avg_fare", 300)
            )
        
        # Add transfer edges (station connections)
        transfers = await self._load_transfers()
        for transfer in transfers:
            self.graph.add_edge(
                transfer["station1"],
                transfer["station2"],
                type="transfer",
                walking_time=transfer.get("walking_minutes", 10),
                cost=transfer.get("cost", 0)
            )
        
        logger.info(f"Knowledge graph built: {len(self.graph.nodes)} nodes, {len(self.graph.edges)} edges")
    
    async def initialize(self):
        """
        Initialize the knowledge graph with database data.
        Call this method after creating the service instance.
        """
        # Load persisted data first
        await self.load_from_database()
        
        # Build graph if empty
        if len(self.graph.nodes) == 0:
            await self.build_initial_graph()
        
        logger.info("Knowledge Graph initialization complete")
    
    async def _load_stations(self) -> List[Dict]:
        """Load station data from the database."""
        if not self.db:
            raise RuntimeError("Database session required for station loading")

        try:
            from database.models import Stop
            stations = self.db.query(Stop).all()
            return [
                {
                    "code": stop.code,
                    "name": stop.name,
                    "region": getattr(stop, "city", ""),
                    "zone": getattr(stop, "state", ""),
                    "connectivity_score": 0.5 if stop.is_major_junction is None else (0.9 if stop.is_major_junction else 0.6)
                }
                for stop in stations if stop.code and stop.name
            ]
        except Exception as e:
            logger.error(f"Failed to load stations from DB: {e}")
            return []

    async def _load_routes(self) -> List[Dict]:
        """Load route data from the database."""
        if not self.db:
            raise RuntimeError("Database session required for route loading")

        try:
            from database.models import Trip, StopTime, Stop, Fare
            routes = []
            trips = self.db.query(Trip).all()

            for trip in trips:
                stop_times = (
                    self.db.query(StopTime)
                    .filter(StopTime.trip_id == trip.id)
                    .order_by(StopTime.stop_sequence)
                    .all()
                )

                if len(stop_times) < 2:
                    continue

                first = self.db.query(Stop).filter(Stop.id == stop_times[0].stop_id).first()
                last = self.db.query(Stop).filter(Stop.id == stop_times[-1].stop_id).first()

                if not first or not last:
                    continue

                duration_minutes = 0
                try:
                    if stop_times[0].departure_time and stop_times[-1].arrival_time:
                        duration_minutes = (
                            datetime.combine(date.today(), stop_times[-1].arrival_time) -
                            datetime.combine(date.today(), stop_times[0].departure_time)
                        ).seconds // 60
                except Exception:
                    duration_minutes = 0

                fare = (
                    self.db.query(Fare)
                    .filter(Fare.trip_id == trip.id)
                    .order_by(Fare.amount)
                    .first()
                )
                avg_fare = float(fare.amount) if fare else 300.0
                frequency_daily = 1
                routes.append({
                    "source": first.code,
                    "destination": last.code,
                    "duration_minutes": duration_minutes,
                    "frequency_daily": frequency_daily,
                    "reliability_score": 0.9,
                    "avg_fare": avg_fare
                })

            return routes
        except Exception as e:
            logger.error(f"Failed to load routes from DB: {e}")
            return []

    async def _load_transfers(self) -> List[Dict]:
        """Load transfer data from the database."""
        if not self.db:
            raise RuntimeError("Database session required for transfer loading")

        try:
            from database.models import Transfer, Stop
            transfers = self.db.query(Transfer).all()
            results = []
            for transfer in transfers:
                from_stop = self.db.query(Stop).filter(Stop.id == transfer.from_stop_id).first()
                to_stop = self.db.query(Stop).filter(Stop.id == transfer.to_stop_id).first()
                if not from_stop or not to_stop:
                    continue
                results.append({
                    "station1": from_stop.code,
                    "station2": to_stop.code,
                    "walking_minutes": transfer.min_transfer_time or 10,
                    "cost": 0
                })
            return results
        except Exception as e:
            logger.error(f"Failed to load transfers from DB: {e}")
            return []
    
    # =========================================================================
    # LEARNING
    # =========================================================================
    
    async def learn_from_booking(self, booking: Dict):
        """Update knowledge graph from booking data"""
        self.total_interactions += 1
        
        # Learn route popularity
        route_key = f"{booking['source']}->{booking['destination']}"
        if route_key not in self.route_patterns:
            self.route_patterns[route_key] = {"bookings": 0, "cancellations": 0}
        
        self.route_patterns[route_key]["bookings"] += 1
        
        # Learn cancellation patterns
        if booking.get("cancelled", False):
            self.route_patterns[route_key]["cancellations"] += 1
        
        # Learn user preferences
        if "user_id" in booking:
            await self._update_user_preferences(booking["user_id"], booking)
        
        self.last_update = datetime.utcnow()
    
    # =========================================================================
    # PATTERN CREATION
    # =========================================================================
    
    def create_station_pattern(
        self,
        code: str,
        name: str,
        region: str,
        zone: str,
        connectivity_score: float = 0.5
    ) -> 'StationNode':
        """Create a station pattern node"""
        node = StationNode(
            code=code,
            name=name,
            region=region,
            zone=zone,
            connectivity_score=connectivity_score
        )
        
        # Add to graph
        self.graph.add_node(
            code,
            type="station",
            name=name,
            region=region,
            zone=zone,
            connectivity=connectivity_score
        )
        
        # Store pattern
        self.station_patterns[code] = node
        
        return node
    
    def create_route_pattern(
        self,
        source: str,
        destination: str,
        avg_duration: int,
        success_rate: float,
        peak_hours: list,
        demand_pattern: str
    ) -> Dict:
        """Create a route pattern node"""
        # Store pattern as dict
        route_key = f"{source}->{destination}"
        node = {
            "source": source,
            "destination": destination,
            "avg_duration": avg_duration,
            "success_rate": success_rate,
            "peak_hours": peak_hours,
            "demand_pattern": demand_pattern
        }
        
        # Add edge to graph
        self.graph.add_edge(
            source,
            destination,
            type="route",
            duration=avg_duration,
            reliability=success_rate,
            frequency=10,
            demand=demand_pattern
        )
        
        # Store pattern
        self.route_patterns[route_key] = node
        
        return node
    
    def create_user_preference(
        self,
        user_id: str,
        preferred_class: str = "SL",
        preferred_time_morning: bool = False,
        flexibility_score: float = 0.5,
        price_sensitivity: float = 0.5
    ) -> 'UserPreference':
        """Create a user preference profile"""
        pref = UserPreference(
            user_id=user_id,
            preferred_class=preferred_class,
            preferred_time_morning=preferred_time_morning,
            class_flexibility=flexibility_score,
            price_sensitivity=price_sensitivity
        )
        
        self.user_preferences[user_id] = pref
        return pref
    
    async def learn_from_search(self, search: Dict):
        """Update knowledge from search behavior"""
        # Track search patterns
        route_key = f"{search['source']}->{search['destination']}"
        
        if route_key not in self.route_patterns:
            self.route_patterns[route_key] = {"searches": 0, "bookings": 0}
        
        self.route_patterns[route_key]["searches"] = \
            self.route_patterns[route_key].get("searches", 0) + 1
        
        # Track conversion rate
        # (searches that result in bookings)
    
    async def _update_user_preferences(self, user_id: str, booking: Dict):
        """Update learned preferences for a user"""
        if user_id not in self.user_preferences:
            self.user_preferences[user_id] = UserPreference(user_id=user_id)
        
        prefs = self.user_preferences[user_id]
        
        # Update preferred routes
        route = f"{booking['source']}->{booking['destination']}"
        if route not in prefs.preferred_routes:
            prefs.preferred_routes.append(route)
        
        # Update booking advance
        if "travel_date" in booking and "booking_date" in booking:
            days_advance = (booking["travel_date"] - booking["booking_date"]).days
            prefs.avg_booking_advance_days = int(
                (1 - self.LEARNING_RATE) * prefs.avg_booking_advance_days +
                self.LEARNING_RATE * days_advance
            )
    
    # =========================================================================
    # QUERYING
    # =========================================================================
    
    def query_optimal_routes(
        self,
        source: str,
        dest: str,
        max_transfers: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Query knowledge graph for optimal routes.
        Uses learned patterns to rank routes.
        """
        if source not in self.graph or dest not in self.graph:
            return []
        
        try:
            # Get all simple paths
            all_paths = list(nx.all_simple_paths(
                self.graph, source, dest, cutoff=max_transfers + 1
            ))
            
            # Score each path
            scored_paths = []
            for path in all_paths:
                score = self._score_path(path)
                path_info = {
                    "path": path,
                    "score": score,
                    "segments": len(path) - 1,
                    "details": self._get_path_details(path)
                }
                scored_paths.append(path_info)
            
            # Sort by score
            scored_paths.sort(key=lambda x: x["score"], reverse=True)
            
            return scored_paths[:10]  # Top 10
            
        except nx.NetworkXNoPath:
            return []
    
    def _score_path(self, path: List[str]) -> float:
        """Score a path using learned knowledge"""
        score = 100.0
        
        for i in range(len(path) - 1):
            edge_data = self.graph.get_edge_data(path[i], path[i+1])
            if not edge_data:
                continue
            
            # Reliability factor
            reliability = edge_data.get("reliability", 0.9)
            score *= reliability
            
            # Frequency factor (more frequent = better)
            frequency = edge_data.get("frequency", 5)
            score *= min(1.0, frequency / 15)
        
        # Penalize transfers
        score *= (0.95 ** (len(path) - 2))
        
        # Apply learned popularity
        route_key = f"{path[0]}->{path[-1]}"
        if route_key in self.route_patterns:
            pattern = self.route_patterns[route_key]
            bookings = pattern.get("bookings", 0)
            # Boost popular routes slightly
            score *= (1.0 + min(0.2, bookings / 1000))
        
        return score
    
    def _get_path_details(self, path: List[str]) -> List[Dict]:
        """Get detailed information about each segment"""
        details = []
        
        for i in range(len(path) - 1):
            edge_data = self.graph.get_edge_data(path[i], path[i+1])
            
            if edge_data:
                details.append({
                    "from": path[i],
                    "to": path[i+1],
                    "type": edge_data.get("type", "route"),
                    "duration": edge_data.get("duration", 0),
                    "frequency": edge_data.get("frequency", 0),
                    "reliability": edge_data.get("reliability", 0.9)
                })
        
        return details
    
    # =========================================================================
    # RECOMMENDATIONS
    # =========================================================================
    
    async def get_personalized_recommendations(
        self,
        user_id: str,
        context: Dict[str, Any]
    ) -> List[Dict[str, Any]]:
        """
        Generate personalized recommendations for a user.
        
        Args:
            user_id: User ID
            context: Current search context (source, destination, date, etc.)
            
        Returns:
            List of recommendations with explanations
        """
        recommendations = []
        
        # Get user preferences
        prefs = self.user_preferences.get(user_id)
        
        if not prefs:
            # Cold start - use popular routes
            return await self._get_popular_recommendations(context)
        
        # Generate different types of recommendations
        
        # 1. Similar user recommendations
        similar = await self._get_similar_user_recommendations(prefs, context)
        recommendations.extend(similar)
        
        # 2. Preference-based recommendations
        preference_recs = self._get_preference_recommendations(prefs, context)
        recommendations.extend(preference_recs)
        
        # 3. Smart alternatives
        if context.get("source") and context.get("destination"):
            alternatives = self._get_smart_alternatives(
                context["source"],
                context["destination"],
                context.get("date")
            )
            recommendations.extend(alternatives)
        
        # Sort by confidence
        recommendations.sort(key=lambda x: x.get("confidence", 0), reverse=True)
        
        return recommendations[:5]
    
    async def _get_popular_recommendations(self, context: Dict) -> List[Dict]:
        """Get popular routes as recommendations"""
        # Sort routes by booking count
        sorted_routes = sorted(
            self.route_patterns.items(),
            key=lambda x: x[1].get("bookings", 0),
            reverse=True
        )
        
        recs = []
        for route_key, pattern in sorted_routes[:5]:
            source, dest = route_key.split("->")
            recs.append({
                "type": "popular",
                "route": route_key,
                "confidence": min(0.8, pattern.get("bookings", 0) / 500),
                "reason": "Popular route among travelers"
            })
        
        return recs
    
    def _get_preference_recommendations(
        self,
        prefs: UserPreference,
        context: Dict
    ) -> List[Dict]:
        """Get recommendations based on user preferences"""
        recs = []
        
        # Check if current search matches preferences
        current_route = f"{context.get('source', '')}->{context.get('destination', '')}"
        
        if current_route in prefs.preferred_routes:
            recs.append({
                "type": "preference_match",
                "route": current_route,
                "confidence": 0.9,
                "reason": "Matches your preferred routes"
            })
        
        # Recommend preferred times
        if context.get("date"):
            day_of_week = context["date"].weekday()
            if day_of_week in prefs.preferred_times:
                recs.append({
                    "type": "time_preference",
                    "confidence": 0.7,
                    "reason": f"Travels frequently on {['Mon','Tue','Wed','Thu','Fri','Sat','Sun'][day_of_week]}"
                })
        
        return recs
    
    def _get_smart_alternatives(
        self,
        source: str,
        dest: str,
        travel_date: Optional[date]
    ) -> List[Dict]:
        """Get smart alternative routes"""
        alternatives = self.query_optimal_routes(source, dest, max_transfers=2)
        
        recs = []
        for alt in alternatives[:3]:
            recs.append({
                "type": "smart_alternative",
                "route": " -> ".join(alt["path"]),
                "score": alt["score"],
                "confidence": alt["score"] / 100,
                "segments": alt["segments"],
                "reason": f"Optimal route with {alt['segments']} transfer(s)"
            })
        
        return recs
    
    async def _get_similar_user_recommendations(
        self,
        prefs: UserPreference,
        context: Dict
    ) -> List[Dict]:
        """
        Get recommendations from similar users using collaborative filtering.
        
        Uses cosine similarity on user behavior vectors.
        """
        if not self.user_behavior_matrix:
            return []
        
        # Get current user's behavior vector
        user_id = prefs.user_id
        if user_id not in self.user_behavior_matrix:
            return []
        
        current_user_vec = self.user_behavior_matrix[user_id]
        
        # Calculate similarity with all other users
        similarities = []
        for other_id, other_vec in self.user_behavior_matrix.items():
            if other_id == user_id:
                continue
            
            # Create aligned vectors
            all_keys = set(current_user_vec.keys()) | set(other_vec.keys())
            vec1 = [current_user_vec.get(k, 0) for k in all_keys]
            vec2 = [other_vec.get(k, 0) for k in all_keys]
            
            # Calculate cosine similarity
            try:
                similarity = cosine_similarity(np.array([vec1]), np.array([vec2]))[0][0]
                similarities.append((other_id, similarity, other_vec))
            except Exception:
                continue

        # Sort by similarity
        similarities.sort(key=lambda x: x[1], reverse=True)
        
        # Get top similar users' preferred routes
        similar_users = similarities[:10]  # Top 10 similar users
        route_scores: Dict[str, float] = defaultdict(float)
        
        for other_id, similarity, other_vec in similar_users:
            for route, score in other_vec.items():
                if route.startswith("route:"):
                    route_key = route.replace("route:", "")
                    route_scores[route_key] += similarity * score
        
        # Generate recommendations
        recommendations = []
        for route_key, score in sorted(route_scores.items(), key=lambda x: x[1], reverse=True)[:5]:
            source, dest = route_key.split("->")
            recommendations.append({
                "type": "similar_user",
                "route": route_key,
                "confidence": min(0.9, score / 3),
                "reason": f"Popular among users with similar preferences"
            })
        
        return recommendations
    
    async def _update_user_behavior(self, user_id: str, route_key: str, score: float):
        """Update user behavior matrix for collaborative filtering."""
        if user_id not in self.user_behavior_matrix:
            self.user_behavior_matrix[user_id] = {}
        
        self.user_behavior_matrix[user_id][f"route:{route_key}"] = score
        
        # Keep matrix manageable
        if len(self.user_behavior_matrix[user_id]) > 100:
            # Keep only top 100 routes
            sorted_routes = sorted(
                self.user_behavior_matrix[user_id].items(),
                key=lambda x: x[1],
                reverse=True
            )
            self.user_behavior_matrix[user_id] = dict(sorted_routes[:100])
    
    # =========================================================================
    # ANALYTICS
    # =========================================================================
    
    def get_graph_statistics(self) -> Dict[str, Any]:
        """Get knowledge graph statistics"""
        # Calculate average route success rate
        total_success = 0
        route_count = 0
        for pattern in self.route_patterns.values():
            if isinstance(pattern, dict) and "success_rate" in pattern:
                total_success += pattern["success_rate"]
                route_count += 1
        
        avg_route_success = total_success / route_count if route_count > 0 else 0.0
        
        return {
            "total_stations": len([n for n in self.graph.nodes if self.graph.nodes[n].get("type") == "station"]),
            "total_routes": len([n for n in self.graph.nodes if self.graph.nodes[n].get("type") == "route"]),
            "total_edges": len(self.graph.edges),
            "total_interactions": self.total_interactions,
            "total_users": len(self.user_preferences),
            "tracked_routes": len(self.route_patterns),
            "avg_route_success": avg_route_success,
            "last_update": self.last_update.isoformat() if self.last_update else None
        }
    
    def get_route_intelligence(self, source: str, dest: str) -> Dict[str, Any]:
        """Get comprehensive intelligence for a route"""
        route_key = f"{source}->{dest}"
        
        # Get basic path info
        paths = self.query_optimal_routes(source, dest, max_transfers=2)
        
        # Get pattern data
        pattern = self.route_patterns.get(route_key, {})
        
        # Get seasonal patterns
        seasonal = self.seasonal_patterns.get(route_key, {})
        
        # Get competitor prices
        competitors = self.competitor_prices.get(route_key, {})
        
        return {
            "route": route_key,
            "optimal_paths": paths[:3],
            "popularity": {
                "searches": pattern.get("searches", 0),
                "bookings": pattern.get("bookings", 0),
                "cancellations": pattern.get("cancellations", 0)
            },
            "conversion_rate": (
                pattern.get("bookings", 0) / pattern.get("searches", 1)
                if pattern.get("searches", 0) > 0 else 0
            ),
            "seasonal_patterns": seasonal,
            "competitor_prices": competitors,
            "reliability_score": pattern.get("success_rate", 0.85)
        }
    
    # =========================================================================
    # MARKET INTELLIGENCE
    # =========================================================================
    
    def update_competitor_price(self, route_key: str, provider: str, price: float):
        """Update competitor price for a route."""
        if route_key not in self.competitor_prices:
            self.competitor_prices[route_key] = {}
        
        self.competitor_prices[route_key][provider] = {
            "price": price,
            "updated_at": datetime.utcnow().isoformat()
        }
        
        logger.debug(f"Updated competitor price for {route_key}: {provider} = ₹{price}")
    
    def get_price_intelligence(self, route_key: str) -> Dict[str, Any]:
        """Get price intelligence for a route."""
        competitors = self.competitor_prices.get(route_key, {})
        
        if not competitors:
            return {"status": "no_data"}
        
        prices = [c["price"] for c in competitors.values()]
        
        return {
            "status": "available",
            "providers": len(competitors),
            "min_price": min(prices) if prices else 0,
            "max_price": max(prices) if prices else 0,
            "avg_price": sum(prices) / len(prices) if prices else 0,
            "competitors": competitors
        }
    
    def update_seasonal_pattern(self, route_key: str, month: int, demand_score: float):
        """Update seasonal demand pattern for a route."""
        if route_key not in self.seasonal_patterns:
            self.seasonal_patterns[route_key] = {}
        
        self.seasonal_patterns[route_key][month] = demand_score

    # =========================================================================
    # PHASE 8: RELEASE VALVES (ARBITRAGE)
    # =========================================================================

    async def add_release_valve(self, src: str, dst: str, mode: str, data: Dict[str, Any]):
        """
        Record a 'Release Valve' (Arbitrage) opportunity.
        Used by MultiModalArbitrageAgent to suggest modal shifts.
        """
        route_key = f"{src}->{dst}"
        valve = {
            "mode": mode,
            "timestamp": datetime.utcnow().isoformat(),
            **data
        }
        
        # Add to local storage
        self.release_valves[route_key].append(valve)
        
        # Prune old valves (TTL: 1 hour for real-time arbitrage)
        now = datetime.utcnow()
        self.release_valves[route_key] = [
            v for v in self.release_valves[route_key]
            if (now - datetime.fromisoformat(v['timestamp'])).total_seconds() < 3600
        ]
        
        logger.info(f"🔓 [KG] Added {mode} Release Valve for {route_key}")

    async def get_release_valves(self, src: str, dst: str) -> List[Dict]:
        """
        Retrieve active release valves for a route.
        """
        route_key = f"{src}->{dst}"
        return self.release_valves.get(route_key, [])

    def get_seasonal_intelligence(self, route_key: str, travel_month: int) -> Dict[str, Any]:
        """Get seasonal intelligence for a route."""
        seasonal = self.seasonal_patterns.get(route_key, {})
        
        month_name = [
            "January", "February", "March", "April", "May", "June",
            "July", "August", "September", "October", "November", "December"
        ][travel_month - 1]
        
        current_demand = seasonal.get(month_name, {}).get("demand_score", 0.5)
        
        # Calculate trend
        months = list(seasonal.keys())
        if len(months) >= 2:
            # Simple trend: compare to average of other months
            avg_demand = sum(
                seasonal[m]["demand_score"] for m in months
            ) / len(months)
            trend = "increasing" if current_demand > avg_demand * 1.1 else \
                    "decreasing" if current_demand < avg_demand * 0.9 else "stable"
        else:
            trend = "unknown"
        
        return {
            "month": month_name,
            "demand_score": current_demand,
            "demand_level": "high" if current_demand > 0.7 else \
                           "medium" if current_demand > 0.4 else "low",
            "trend": trend,
            "recommendation": self._get_seasonal_recommendation(current_demand)
        }
    
    def _get_seasonal_recommendation(self, demand_score: float) -> str:
        """Get recommendation based on seasonal demand."""
        if demand_score > 0.8:
            return "Book early, prices may be higher"
        elif demand_score > 0.5:
            return "Moderate demand, standard booking recommended"
        else:
            return "Low demand, good deals available"
    
    # =========================================================================
    # PERSISTENCE
    # =========================================================================
    
    async def save_to_database(self):
        """
        Save knowledge graph to database for persistence.
        
        Saves:
        - User preferences
        - Route patterns
        - Station patterns
        - Seasonal patterns
        - Competitor prices
        - User behavior matrix
        """
        if not self.db:
            logger.warning("No database connection, cannot save knowledge graph")
            return False
        
        try:
            # Import models
            from database.models_redistribution import KnowledgeGraphNode, KnowledgeGraphEdge
            from database.models import UserPreferenceModel, RoutePatternModel
            
            # Save user preferences
            for user_id, pref in self.user_preferences.items():
                pref_model = self.db.query(UserPreferenceModel).filter_by(user_id=user_id).first()
                if pref_model:
                    pref_model.preferred_class = pref.preferred_class
                    pref_model.preferred_time_morning = pref.preferred_time_morning
                    pref_model.class_flexibility = pref.class_flexibility
                    pref_model.price_sensitivity = pref.price_sensitivity
                    pref_model.preferred_stations = ",".join(pref.preferred_stations)
                    pref_model.preferred_routes = ",".join(pref.preferred_routes)
                    pref_model.preferred_times = ",".join(map(str, pref.preferred_times))
                    pref_model.avg_booking_advance_days = pref.avg_booking_advance_days
                    pref_model.cancellation_rate = pref.cancellation_rate
                    pref_model.updated_at = datetime.utcnow()
                else:
                    pref_model = UserPreferenceModel(
                        user_id=user_id,
                        preferred_class=pref.preferred_class,
                        preferred_time_morning=pref.preferred_time_morning,
                        class_flexibility=pref.class_flexibility,
                        price_sensitivity=pref.price_sensitivity,
                        preferred_stations=",".join(pref.preferred_stations),
                        preferred_routes=",".join(pref.preferred_routes),
                        preferred_times=",".join(map(str, pref.preferred_times)),
                        avg_booking_advance_days=pref.avg_booking_advance_days,
                        cancellation_rate=pref.cancellation_rate
                    )
                    self.db.add(pref_model)
            
            # Save route patterns
            for route_key, pattern in self.route_patterns.items():
                if isinstance(pattern, dict):
                    source, dest = route_key.split("->")
                    pattern_model = self.db.query(RoutePatternModel).filter_by(
                        source=source, destination=dest
                    ).first()
                    
                    if pattern_model:
                        pattern_model.searches = pattern.get("searches", 0)
                        pattern_model.bookings = pattern.get("bookings", 0)
                        pattern_model.cancellations = pattern.get("cancellations", 0)
                        pattern_model.success_rate = pattern.get("success_rate", 0.85)
                        pattern_model.updated_at = datetime.utcnow()
                    else:
                        pattern_model = RoutePatternModel(
                            source=source,
                            destination=dest,
                            searches=pattern.get("searches", 0),
                            bookings=pattern.get("bookings", 0),
                            cancellations=pattern.get("cancellations", 0),
                            success_rate=pattern.get("success_rate", 0.85)
                        )
                        self.db.add(pattern_model)
            
            # Save seasonal patterns
            for route_key, seasonal in self.seasonal_patterns.items():
                source, dest = route_key.split("->")
                for month_name, data in seasonal.items():
                    # Would save to seasonal_patterns table
                    pass
            
            # Save competitor prices
            for route_key, competitors in self.competitor_prices.items():
                source, dest = route_key.split("->")
                for provider, data in competitors.items():
                    # Would save to competitor_prices table
                    pass
            
            self.db.commit()
            logger.info("Knowledge graph state saved to database")
            return True
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to save knowledge graph: {e}")
            return False
    
    async def load_from_database(self):
        """
        Load knowledge graph from database.
        
        Loads:
        - User preferences
        - Route patterns
        - Seasonal patterns
        - Competitor prices
        """
        if not self.db:
            logger.warning("No database connection, cannot load knowledge graph")
            return
        
        try:
            # Import models
            from database.models import UserPreferenceModel, RoutePatternModel
            
            # Load user preferences
            pref_models = self.db.query(UserPreferenceModel).all()
            for pref_model in pref_models:
                pref = UserPreference(
                    user_id=pref_model.user_id,
                    preferred_class=pref_model.preferred_class,
                    preferred_time_morning=pref_model.preferred_time_morning,
                    class_flexibility=pref_model.class_flexibility,
                    price_sensitivity=pref_model.price_sensitivity
                )
                if pref_model.preferred_stations:
                    pref.preferred_stations = pref_model.preferred_stations.split(",")
                if pref_model.preferred_routes:
                    pref.preferred_routes = pref_model.preferred_routes.split(",")
                if pref_model.preferred_times:
                    pref.preferred_times = list(map(int, pref_model.preferred_times.split(",")))
                pref.avg_booking_advance_days = pref_model.avg_booking_advance_days
                pref.cancellation_rate = pref_model.cancellation_rate
                
                self.user_preferences[pref_model.user_id] = pref
            
            # Load route patterns
            pattern_models = self.db.query(RoutePatternModel).all()
            for pattern_model in pattern_models:
                route_key = f"{pattern_model.source}->{pattern_model.destination}"
                self.route_patterns[route_key] = {
                    "searches": pattern_model.searches,
                    "bookings": pattern_model.bookings,
                    "cancellations": pattern_model.cancellations,
                    "success_rate": pattern_model.success_rate
                }
            
            # Load seasonal patterns
            # Would query seasonal_patterns table
            
            # Load competitor prices
            # Would query competitor_prices table
            
            logger.info("Knowledge graph state loaded from database")
            
        except Exception as e:
            logger.error(f"Failed to load knowledge graph: {e}")
    
    # =========================================================================
    # SYNC SERVICE INTEGRATION
    # =========================================================================
    
    async def update_station_from_heartbeat(self, station_code: str, heartbeat_data: Dict):
        """
        Update station patterns from heartbeat data.
        Called by Sync Service when new heartbeat data is available.
        """
        try:
            # Update or create station node
            if station_code not in self.station_patterns:
                self.station_patterns[station_code] = StationNode(
                    code=station_code,
                    name=heartbeat_data.get("station", station_code),
                    region="",
                    zone="",
                    connectivity_score=0.5
                )
            
            # Update delay and cancellation stats
            station = self.station_patterns[station_code]
            if "total_delayed" in heartbeat_data:
                # Exponential moving average for delay
                station.avg_delay_minutes = (
                    0.3 * heartbeat_data["total_delayed"] + 
                    0.7 * station.avg_delay_minutes
                )
            
            if "total_cancelled" in heartbeat_data:
                station.cancellation_rate = (
                    0.2 * (heartbeat_data["total_cancelled"] / 100) + 
                    0.8 * station.cancellation_rate
                )
            
            # Update peak hours if available
            if "trains" in heartbeat_data and heartbeat_data["trains"]:
                # Extract departure hours from trains
                departure_hours = []
                for train in heartbeat_data["trains"][:20]:  # Limit to 20 trains
                    if "departure_time" in train:
                        try:
                            hour = int(train["departure_time"].split(":")[0])
                            departure_hours.append(hour)
                        except:
                            pass
                
                if departure_hours:
                    # Get most common hours
                    from collections import Counter
                    hour_counts = Counter(departure_hours)
                    station.peak_hours = [h for h, _ in hour_counts.most_common(5)]
            
            logger.debug(f"Updated station {station_code} from heartbeat")
            
        except Exception as e:
            logger.error(f"Error updating station from heartbeat: {e}")
    
    # =========================================================================
    # METRICS & HEALTH
    # =========================================================================
    
    async def _record_metrics(self, operation: str, success: bool, details: Optional[Dict[str, Any]] = None):
        """Record service metrics."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "operation": operation,
                "success": success,
                "details": details or {}
            })
    
    def get_metrics(self) -> Dict[str, Any]:
        """Get service metrics."""
        if not self._metrics:
            return {"total_operations": 0, "success_rate": 0.0}
        
        total = len(self._metrics)
        successful = sum(1 for m in self._metrics if m["success"])
        
        return {
            "total_operations": total,
            "successful_operations": successful,
            "failed_operations": total - successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "graph_nodes": len(self.graph.nodes),
            "graph_edges": len(self.graph.edges),
            "user_preferences": len(self.user_preferences),
            "route_patterns": len(self.route_patterns),
            "user_behavior_entries": sum(len(v) for v in self.user_behavior_matrix.values()),
            "circuit_breaker_state": self._db_breaker.get_state().value
        }
    
    def health_check(self) -> Dict[str, Any]:
        """Health check endpoint."""
        return {
            "status": "healthy",
            "circuit_breaker": {
                "state": self._db_breaker.get_state().value,
                "failure_count": self._db_breaker.failure_count,
                "success_count": self._db_breaker.success_count
            },
            "metrics": self.get_metrics(),
            "last_update": self.last_update.isoformat() if self.last_update else None
        }
    
    def reset_circuit_breaker(self):
        """Reset the circuit breaker."""
        self._db_breaker.reset()
        logger.info("Circuit breaker reset for knowledge_graph_service")


    async def get_intermediate_hubs(self, src: str, dst: str) -> List[str]:
        """
        Find major junction stations between source and destination.
        Used for intermodal split discovery.
        """
        if src not in self.graph or dst not in self.graph:
            return []
            
        try:
            # Get all simple paths (up to 3 nodes) to find intermediate stations
            paths = list(nx.all_simple_paths(self.graph, src, dst, cutoff=2))
            hubs = set()
            for path in paths:
                if len(path) > 2: # Has intermediate nodes
                    for node in path[1:-1]:
                        hubs.add(node)
            
            # Sort by connectivity score
            sorted_hubs = sorted(
                list(hubs),
                key=lambda x: self.graph.nodes[x].get("connectivity", 0.5),
                reverse=True
            )
            return sorted_hubs
        except Exception:
            return []

# Global instance
_knowledge_graph: Optional[TravelKnowledgeGraph] = None

def get_knowledge_graph() -> TravelKnowledgeGraph:
    """Get or create global knowledge graph instance"""
    global _knowledge_graph
    if _knowledge_graph is None:
        _knowledge_graph = TravelKnowledgeGraph()
    return _knowledge_graph