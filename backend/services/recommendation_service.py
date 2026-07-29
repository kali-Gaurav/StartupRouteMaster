"""
Recommendation Service - Personalized Journey Suggestions
Implements candidate generation, ranking, and filtering for Feature #5.

Recommendation Algorithm:
1. Candidate Generation from 4 sources:
   - User preferred routes (history-based)
   - Similar routes (network-based)
   - Trending routes (popularity-based)
   - High-availability routes (supply-based)
2. Ranking with weighted factors
3. Personalization and filtering
4. Caching for performance
"""

import logging
from typing import List, Dict, Optional, Any, Tuple
from datetime import datetime, timedelta
from uuid import uuid4
import asyncio

from sqlalchemy.orm import Session
from sqlalchemy import select, func, and_

from database.models import RouteKnowledge, UserTravelPreference, DemandSnapshot, SearchOutcome
from core.data_utils.structures import Route, Persona

logger = logging.getLogger(__name__)

# Lazy import to avoid dependency issues in tests
SearchService = None


class RecommendationEngine:
    """Engine for generating personalized route recommendations."""

    def __init__(self, db: Optional[Session] = None, search_service: Optional[Any] = None):
        self.db = db
        self.search_service = search_service
        self._cache: Dict[str, Tuple[List[Route], datetime]] = {}
        self._cache_ttl = timedelta(minutes=5)

    def _cache_key(self, user_id: str, source: str, dest: str, travel_date: str) -> str:
        """Generate cache key for recommendations."""
        return f"rec:{user_id}:{source}:{dest}:{travel_date}"

    def _get_cached(self, key: str) -> Optional[List[Route]]:
        """Get recommendations from cache if fresh."""
        if key in self._cache:
            routes, timestamp = self._cache[key]
            if datetime.now() - timestamp < self._cache_ttl:
                return routes
            del self._cache[key]
        return None

    def _set_cached(self, key: str, routes: List[Route]):
        """Cache recommendations."""
        self._cache[key] = (routes, datetime.now())

    async def get_recommendations(
        self,
        user_id: str,
        source: str,
        destination: str,
        travel_date: str,
        persona: Persona = Persona.COMFORT,
        limit: int = 10
    ) -> Dict[str, Any]:
        """
        Generate personalized recommendations for a user.

        Args:
            user_id: User ID for personalization
            source: Origin station code
            destination: Destination station code
            travel_date: Travel date (YYYY-MM-DD)
            persona: User persona for ranking
            limit: Number of recommendations to return

        Returns:
            {
                "recommendations": [route_dict, ...],
                "reasons": ["Based on your preferences", "Trending route", ...],
                "metadata": {
                    "generated_at": datetime,
                    "algorithm_version": "1.0",
                    "confidence_scores": [0.95, 0.87, ...]
                }
            }
        """
        cache_key = self._cache_key(user_id, source, destination, travel_date)
        cached = self._get_cached(cache_key)
        if cached:
            logger.info(f"Returning cached recommendations for {user_id}")
            return self._format_response(cached, "cached", persona)

        try:
            # Phase 1: Generate candidates from 4 sources
            candidates = await self._generate_candidates(
                user_id, source, destination, travel_date, persona
            )

            if not candidates:
                logger.warning(f"No candidates for {source}->{destination} on {travel_date}")
                return {
                    "recommendations": [],
                    "reasons": ["No routes available on this date"],
                    "metadata": {"generated_at": datetime.now().isoformat(), "confidence_scores": []}
                }

            # Phase 2: Rank candidates
            ranked = await self._rank_candidates(candidates, user_id, persona)

            # Phase 3: Filter and format
            final_recommendations = ranked[:limit]
            self._set_cached(cache_key, final_recommendations)

            return self._format_response(final_recommendations, "generated", persona)

        except Exception as e:
            logger.error(f"Recommendation generation failed: {e}")
            return {
                "recommendations": [],
                "reasons": ["Service temporarily unavailable"],
                "metadata": {"error": str(e), "generated_at": datetime.now().isoformat()}
            }

    async def _generate_candidates(
        self,
        user_id: str,
        source: str,
        destination: str,
        travel_date: str,
        persona: Persona
    ) -> List[Route]:
        """
        Generate candidate routes from 4 sources:
        1. User preferred routes
        2. Similar/complementary routes
        3. Trending routes
        4. High-availability routes
        """
        candidates = []

        # Source 1: User Preferred Routes (history-based)
        preferred = await self._get_preferred_routes(user_id, source, destination)
        candidates.extend(preferred)

        # Source 2: Similar Routes (network-based)
        similar = await self._get_similar_routes(source, destination)
        candidates.extend(similar)

        # Source 3: Trending Routes (popularity-based)
        trending = await self._get_trending_routes(source, destination, travel_date)
        candidates.extend(trending)

        # Source 4: High-Availability Routes (supply-based)
        high_avail = await self._get_high_availability_routes(source, destination, travel_date)
        candidates.extend(high_avail)

        # Deduplicate by journey_id
        seen = set()
        unique_candidates = []
        for c in candidates:
            if c.journey_id not in seen:
                unique_candidates.append(c)
                seen.add(c.journey_id)

        logger.info(f"Generated {len(unique_candidates)} unique candidate routes for {source}->{destination}")
        return unique_candidates

    async def _get_preferred_routes(self, user_id: str, source: str, destination: str) -> List[Route]:
        """
        Get routes based on user's historical preferences.
        Query UserTravelPreference to find similar source-destination pairs.
        """
        if not self.db:
            return []

        try:
            pref = self.db.execute(
                select(UserTravelPreference).where(
                    UserTravelPreference.user_id == user_id
                )
            ).scalar_one_or_none()

            if not pref or not pref.preferred_routes:
                return []

            # Filter for routes from same source or within same region
            candidates = []
            for route in pref.preferred_routes:
                if route.get("source") == source:  # Same origin
                    # Query by source-dest pair
                    routes = await self._query_routes_by_pair(source, destination)
                    candidates.extend(routes)

            return candidates[:5]  # Top 5 preferred

        except Exception as e:
            logger.warning(f"Error fetching preferred routes: {e}")
            return []

    async def _get_similar_routes(self, source: str, destination: str) -> List[Route]:
        """
        Find similar routes through the knowledge graph.
        Two routes are similar if they share intermediate stations or have similar duration.
        """
        if not self.db:
            return []

        try:
            # Query RouteKnowledge for routes with similar characteristics
            base_route = self.db.execute(
                select(RouteKnowledge).where(
                    and_(
                        RouteKnowledge.source_code == source,
                        RouteKnowledge.destination_code == destination
                    )
                )
            ).scalar_one_or_none()

            if not base_route:
                return []

            # Find routes with similar duration (±30 minutes)
            min_dur = base_route.duration_minutes - 30
            max_dur = base_route.duration_minutes + 30

            similar_routes = self.db.execute(
                select(RouteKnowledge).where(
                    and_(
                        RouteKnowledge.duration_minutes >= min_dur,
                        RouteKnowledge.duration_minutes <= max_dur,
                        RouteKnowledge.reliability_score >= 0.75
                    )
                ).limit(5)
            ).scalars().all()

            candidates = []
            for sr in similar_routes:
                routes = await self._query_routes_by_pair(sr.source_code, sr.destination_code)
                candidates.extend(routes)

            return candidates

        except Exception as e:
            logger.warning(f"Error fetching similar routes: {e}")
            return []

    async def _get_trending_routes(self, source: str, destination: str, travel_date: str) -> List[Route]:
        """
        Get trending routes based on recent search activity and demand.
        Routes with high search count and good availability score are trending.
        """
        if not self.db:
            return []

        try:
            dt = datetime.strptime(travel_date, "%Y-%m-%d").date()

            # Query DemandSnapshot for high-demand routes
            trending = self.db.execute(
                select(DemandSnapshot).where(
                    and_(
                        DemandSnapshot.source_code == source,
                        DemandSnapshot.destination_code == destination,
                        DemandSnapshot.travel_date == dt,
                        DemandSnapshot.demand_score >= 0.7
                    )
                ).order_by(DemandSnapshot.search_count.desc()).limit(5)
            ).scalars().all()

            candidates = []
            for t in trending:
                routes = await self._query_routes_by_pair(t.source_code, t.destination_code)
                candidates.extend(routes)

            return candidates

        except Exception as e:
            logger.warning(f"Error fetching trending routes: {e}")
            return []

    async def _get_high_availability_routes(self, source: str, destination: str, travel_date: str) -> List[Route]:
        """
        Get routes with high seat availability on the travel date.
        These are good recommendations to improve booking success.
        """
        if not self.db:
            return []

        try:
            dt = datetime.strptime(travel_date, "%Y-%m-%d").date()

            # Query SearchOutcome for routes with high confirmation chances
            high_avail = self.db.execute(
                select(SearchOutcome).where(
                    SearchOutcome.predicted_confirm_chance >= 0.8
                ).order_by(SearchOutcome.predicted_confirm_chance.desc()).limit(5)
            ).scalars().all()

            candidates = []
            for ha in high_avail:
                # Load route metadata from snapshot
                if ha.metadata_snapshot:
                    try:
                        route_dict = ha.metadata_snapshot
                        route = Route.from_dict(route_dict)
                        candidates.append(route)
                    except:
                        pass

            return candidates

        except Exception as e:
            logger.warning(f"Error fetching high-availability routes: {e}")
            return []

    async def _query_routes_by_pair(self, source: str, destination: str) -> List[Route]:
        """
        Query the search service for routes between two stations.
        Helper method to fetch actual Route objects.
        """
        try:
            # Lazy-load SearchService if needed
            if not self.search_service:
                try:
                    from services.search.service import SearchService as SS
                    self.search_service = SS(self.db)
                except ImportError:
                    logger.warning("SearchService unavailable. Skipping route query.")
                    return []

            travel_date = datetime.now().strftime("%Y-%m-%d")
            result = await self.search_service.search_routes(
                source=source,
                destination=destination,
                travel_date=travel_date,
                limit=5
            )

            routes = []
            if result.get("data", {}).get("journeys"):
                for j in result["data"]["journeys"]:
                    try:
                        route = Route.from_dict(j)
                        routes.append(route)
                    except:
                        pass

            return routes

        except Exception as e:
            logger.debug(f"Error querying routes {source}->{destination}: {e}")
            return []

    async def _rank_candidates(self, candidates: List[Route], user_id: str, persona: Persona) -> List[Route]:
        """
        Rank candidates using weighted scoring:
        - Timing alignment (user's preferred hours)
        - Availability (seat availability probability)
        - Price (persona-based budget)
        - Reliability (historical on-time performance)
        - Comfort (passenger ratings)
        """
        scored = []

        # Get user preferences for personalization
        user_pref = self._get_user_preferences(user_id) if self.db else {}

        for candidate in candidates:
            score = self._calculate_recommendation_score(
                candidate, persona, user_pref
            )
            candidate.metadata["recommendation_score"] = score
            scored.append((candidate, score))

        # Sort by score descending
        scored.sort(key=lambda x: x[1], reverse=True)
        return [r for r, _ in scored]

    def _calculate_recommendation_score(
        self,
        route: Route,
        persona: Persona,
        user_pref: Dict[str, Any]
    ) -> float:
        """
        Calculate recommendation score using 5 weighted factors:
        - Timing (30%): Alignment with user's preferred departure hours
        - Availability (25%): Seat availability probability
        - Price (25%): Price alignment with persona budget
        - Reliability (10%): Historical on-time performance
        - Comfort (10%): Passenger ratings and amenities
        """
        weights = {
            "timing": 0.30,
            "availability": 0.25,
            "price": 0.25,
            "reliability": 0.10,
            "comfort": 0.10
        }

        # Score timing (0-1): How well does departure time match preferences?
        timing_score = self._score_timing(route, user_pref)

        # Score availability (0-1)
        availability_score = getattr(route, "availability_probability", 0.7)

        # Score price (0-1): How well does price fit persona?
        price_score = self._score_price(route, persona)

        # Score reliability (0-1): On-time performance
        reliability_score = getattr(route, "reliability_score", 0.85)

        # Score comfort (0-1): Based on route metadata
        comfort_score = self._score_comfort(route)

        # Weighted sum
        total_score = (
            weights["timing"] * timing_score +
            weights["availability"] * availability_score +
            weights["price"] * price_score +
            weights["reliability"] * reliability_score +
            weights["comfort"] * comfort_score
        )

        return min(1.0, max(0.0, total_score))

    def _score_timing(self, route: Route, user_pref: Dict[str, Any]) -> float:
        """
        Score timing based on user's preferred departure hours.
        Default: all times are equally good (0.7 baseline).
        """
        if not route.segments:
            return 0.7

        dep_hour = route.segments[0].departure_time.hour
        preferred_hours = user_pref.get("preferred_hours", list(range(24)))

        if dep_hour in preferred_hours:
            return 0.95

        # Within 2 hours of preferred: 0.8
        for ph in preferred_hours:
            if abs(dep_hour - ph) <= 2:
                return 0.8

        return 0.7

    def _score_price(self, route: Route, persona: Persona) -> float:
        """
        Score price based on persona's expected budget range.
        Personas have different budget tolerances.
        """
        price = getattr(route, "total_cost", 0)

        # Define budget ranges by persona
        budget_ranges = {
            Persona.ECONOMY: (500, 2000),
            Persona.BUDGET: (500, 2000),
            Persona.COMFORT: (2000, 5000),
            Persona.STANDARD: (2000, 5000),
            Persona.PREMIUM: (5000, 15000),
            Persona.FAMILY: (1500, 4000),
            Persona.FAST: (3000, 8000),
            Persona.EMERGENCY: (5000, 12000),
        }

        min_budget, max_budget = budget_ranges.get(persona, (1000, 5000))

        if price < min_budget:
            return 0.8  # Slightly less attractive if too cheap (quality concerns)
        elif price <= max_budget:
            return 0.95  # Perfect alignment
        else:
            # Over budget: score decreases linearly
            overage = price - max_budget
            penalty = min(0.95, overage / max_budget)
            return max(0.3, 0.95 - penalty)

    def _score_comfort(self, route: Route) -> float:
        """
        Score comfort based on route characteristics.
        Direct routes are more comfortable than multi-transfer routes.
        """
        transfers = len(getattr(route, "transfers", []))

        if transfers == 0:
            return 0.95  # Direct routes are most comfortable
        elif transfers == 1:
            return 0.85
        elif transfers == 2:
            return 0.70
        else:
            return 0.50

    def _get_user_preferences(self, user_id: str) -> Dict[str, Any]:
        """Get user travel preferences from database."""
        if not self.db:
            return {}

        try:
            pref = self.db.execute(
                select(UserTravelPreference).where(
                    UserTravelPreference.user_id == user_id
                )
            ).scalar_one_or_none()

            if pref:
                return {
                    "preferred_hours": pref.preferred_departure_hours or list(range(24)),
                    "preferred_class": pref.preferred_class,
                    "price_sensitivity": pref.price_sensitivity,
                    "preferred_routes": pref.preferred_routes or []
                }
        except:
            pass

        return {}

    def _format_response(
        self,
        recommendations: List[Route],
        source: str,
        persona: Persona
    ) -> Dict[str, Any]:
        """Format recommendations for API response."""
        rec_dicts = []
        confidence_scores = []
        reasons = []

        for rec in recommendations:
            try:
                rec_dict = rec.to_dict() if hasattr(rec, "to_dict") else rec
                score = rec.metadata.get("recommendation_score", 0.8) if hasattr(rec, "metadata") else 0.8

                rec_dicts.append(rec_dict)
                confidence_scores.append(score)

                # Generate reason
                reason = self._get_recommendation_reason(rec, persona)
                reasons.append(reason)
            except:
                pass

        return {
            "recommendations": rec_dicts,
            "reasons": reasons,
            "metadata": {
                "generated_at": datetime.now().isoformat(),
                "algorithm_version": "1.0",
                "source": source,
                "persona": persona.value if isinstance(persona, Persona) else str(persona),
                "confidence_scores": confidence_scores
            }
        }

    def _get_recommendation_reason(self, route: Route, persona: Persona) -> str:
        """Generate human-readable reason for recommendation."""
        if hasattr(route, "metadata"):
            if route.metadata.get("is_trending"):
                return "🔥 Trending route with high search volume"
            if route.metadata.get("high_availability"):
                return "✅ Excellent seat availability"
            if len(getattr(route, "transfers", [])) == 0:
                return "✈️ Direct route - most convenient"

        return "Based on your preferences and search history"


# Singleton instance
_recommendation_engine = None


def get_recommendation_engine(db: Optional[Session] = None) -> RecommendationEngine:
    """Get or create recommendation engine instance."""
    global _recommendation_engine
    if _recommendation_engine is None:
        _recommendation_engine = RecommendationEngine(db)
    return _recommendation_engine
