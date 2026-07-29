"""
Unit tests for Recommendation Service
Tests candidate generation, ranking, and recommendation algorithms.
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from sqlalchemy.orm import Session

from services.recommendation_service import RecommendationEngine
from core.data_utils.structures import Route, Persona, Segment, TransferConnection


@pytest.fixture
def mock_db():
    """Mock database session."""
    return Mock(spec=Session)


@pytest.fixture
def mock_search_service():
    """Mock search service."""
    return AsyncMock()


@pytest.fixture
def recommendation_engine(mock_db, mock_search_service):
    """Create RecommendationEngine instance with mocks."""
    return RecommendationEngine(db=mock_db, search_service=mock_search_service)


@pytest.fixture
def mock_route():
    """Create a mock route for testing."""
    route = Mock(spec=Route)
    route.journey_id = "route_123"
    route.segments = [
        Mock(
            trip_id="trip_1",
            train_number="12345",
            departure_code="NDLS",
            arrival_code="BCT",
            departure_time=datetime.now() + timedelta(hours=8),
            arrival_time=datetime.now() + timedelta(hours=14),
            distance_km=300
        )
    ]
    route.transfers = []
    route.total_cost = 2500.0
    route.availability_probability = 0.9
    route.reliability_score = 0.85
    route.to_dict = Mock(return_value={
        "journey_id": "route_123",
        "legs": [],
        "total_cost": 2500.0,
        "num_transfers": 0
    })
    route.metadata = {"recommendation_score": 0.85}
    return route


class TestRecommendationEngineInit:
    """Test recommendation engine initialization."""

    def test_init_with_db(self, mock_db):
        """Test engine initialization with database."""
        engine = RecommendationEngine(db=mock_db)
        assert engine.db == mock_db
        assert engine._cache == {}
        assert engine._cache_ttl == timedelta(minutes=5)

    def test_init_without_db(self):
        """Test engine initialization without database."""
        engine = RecommendationEngine(db=None)
        assert engine.db is None


class TestCaching:
    """Test caching functionality."""

    def test_cache_key_generation(self, recommendation_engine):
        """Test cache key is generated correctly."""
        key = recommendation_engine._cache_key("user123", "NDLS", "BCT", "2026-06-10")
        assert key == "rec:user123:NDLS:BCT:2026-06-10"

    def test_cache_set_and_get(self, recommendation_engine, mock_route):
        """Test setting and retrieving from cache."""
        key = recommendation_engine._cache_key("user123", "NDLS", "BCT", "2026-06-10")
        routes = [mock_route]

        # Set cache
        recommendation_engine._set_cached(key, routes)
        assert key in recommendation_engine._cache

        # Get cache
        cached = recommendation_engine._get_cached(key)
        assert cached == routes

    def test_cache_ttl_expiry(self, recommendation_engine, mock_route):
        """Test cache expires after TTL."""
        key = "test_key"
        routes = [mock_route]

        recommendation_engine._set_cached(key, routes)
        # Manually set old timestamp
        old_timestamp = datetime.now() - timedelta(minutes=10)
        recommendation_engine._cache[key] = (routes, old_timestamp)

        # Should be expired
        cached = recommendation_engine._get_cached(key)
        assert cached is None


class TestScoring:
    """Test recommendation scoring algorithms."""

    def test_score_timing_preferred_hours(self, recommendation_engine):
        """Test timing score for preferred departure hours."""
        route = Mock(spec=Route)
        route.segments = [Mock(departure_time=datetime.now().replace(hour=8))]  # 8 AM
        user_pref = {"preferred_hours": [7, 8, 9]}

        score = recommendation_engine._score_timing(route, user_pref)
        assert score >= 0.90  # Preferred hour (around 0.95)

    def test_score_timing_close_to_preferred(self, recommendation_engine):
        """Test timing score for hours close to preferred."""
        route = Mock(spec=Route)
        route.segments = [Mock(departure_time=datetime.now().replace(hour=9))]  # 9 AM
        user_pref = {"preferred_hours": [7, 8]}  # Prefer 7-8

        score = recommendation_engine._score_timing(route, user_pref)
        assert score == 0.8  # Within 2 hours

    def test_score_timing_no_preference(self, recommendation_engine):
        """Test timing score with no hour preference."""
        route = Mock(spec=Route)
        route.segments = [Mock(departure_time=datetime.now().replace(hour=15))]
        user_pref = {}

        score = recommendation_engine._score_timing(route, user_pref)
        assert 0.5 <= score <= 0.95

    def test_score_price_within_budget(self, recommendation_engine):
        """Test price score when route is within persona budget."""
        route = Mock(spec=Route)
        route.total_cost = 3000  # Within COMFORT range (2000-5000)

        score = recommendation_engine._score_price(route, Persona.COMFORT)
        assert score == 0.95  # Perfect alignment

    def test_score_price_over_budget(self, recommendation_engine):
        """Test price score when route exceeds persona budget."""
        route = Mock(spec=Route)
        route.total_cost = 7000  # Over COMFORT range (2000-5000)

        score = recommendation_engine._score_price(route, Persona.COMFORT)
        assert 0.3 <= score < 0.95  # Penalized but not zero

    def test_score_price_too_cheap(self, recommendation_engine):
        """Test price score when route is suspiciously cheap."""
        route = Mock(spec=Route)
        route.total_cost = 200  # Below COMFORT range

        score = recommendation_engine._score_price(route, Persona.COMFORT)
        assert score == 0.8  # Slight penalty

    def test_score_comfort_direct_route(self, recommendation_engine):
        """Test comfort score for direct route."""
        route = Mock(spec=Route)
        route.transfers = []

        score = recommendation_engine._score_comfort(route)
        assert score == 0.95

    def test_score_comfort_one_transfer(self, recommendation_engine):
        """Test comfort score for one transfer."""
        route = Mock(spec=Route)
        route.transfers = [Mock()]

        score = recommendation_engine._score_comfort(route)
        assert score == 0.85

    def test_score_comfort_multiple_transfers(self, recommendation_engine):
        """Test comfort score decreases with transfers."""
        route = Mock(spec=Route)
        route.transfers = [Mock(), Mock(), Mock()]

        score = recommendation_engine._score_comfort(route)
        assert score == 0.50


class TestRecommendationScore:
    """Test overall recommendation scoring."""

    def test_calculate_recommendation_score(self, recommendation_engine, mock_route):
        """Test overall recommendation score calculation."""
        mock_route.segments = [Mock(departure_time=datetime.now().replace(hour=8))]
        mock_route.total_cost = 3000
        mock_route.transfers = []
        mock_route.availability_probability = 0.9
        mock_route.reliability_score = 0.85

        user_pref = {"preferred_hours": [8, 9]}

        score = recommendation_engine._calculate_recommendation_score(
            mock_route, Persona.COMFORT, user_pref
        )

        # Score should be between 0 and 1
        assert 0.0 <= score <= 1.0
        # High quality route should have high score
        assert score > 0.75

    def test_score_weighting(self, recommendation_engine, mock_route):
        """Test that all factors are weighted correctly."""
        # Create two routes: one excellent, one poor
        good_route = Mock(spec=Route)
        good_route.segments = [Mock(departure_time=datetime.now().replace(hour=8))]
        good_route.total_cost = 2500
        good_route.transfers = []
        good_route.availability_probability = 0.95
        good_route.reliability_score = 0.95

        poor_route = Mock(spec=Route)
        poor_route.segments = [Mock(departure_time=datetime.now().replace(hour=20))]
        poor_route.total_cost = 10000
        poor_route.transfers = [Mock(), Mock(), Mock()]
        poor_route.availability_probability = 0.4
        poor_route.reliability_score = 0.5

        user_pref = {"preferred_hours": [8, 9]}

        good_score = recommendation_engine._calculate_recommendation_score(
            good_route, Persona.COMFORT, user_pref
        )
        poor_score = recommendation_engine._calculate_recommendation_score(
            poor_route, Persona.COMFORT, user_pref
        )

        # Good route should score higher
        assert good_score > poor_score


class TestCandidateGeneration:
    """Test candidate generation from multiple sources."""

    @pytest.mark.asyncio
    async def test_get_preferred_routes_no_db(self, recommendation_engine):
        """Test preferred routes returns empty when no DB."""
        recommendation_engine.db = None
        routes = await recommendation_engine._get_preferred_routes("user123", "NDLS", "BCT")
        assert routes == []

    @pytest.mark.asyncio
    async def test_get_similar_routes_no_db(self, recommendation_engine):
        """Test similar routes returns empty when no DB."""
        recommendation_engine.db = None
        routes = await recommendation_engine._get_similar_routes("NDLS", "BCT")
        assert routes == []

    @pytest.mark.asyncio
    async def test_generate_candidates_empty(self, recommendation_engine):
        """Test candidate generation handles empty results."""
        recommendation_engine.db = None

        candidates = await recommendation_engine._generate_candidates(
            user_id="user123",
            source="NDLS",
            destination="BCT",
            travel_date="2026-06-10",
            persona=Persona.COMFORT
        )

        assert isinstance(candidates, list)


class TestRanking:
    """Test ranking algorithm."""

    @pytest.mark.asyncio
    async def test_rank_candidates_empty_list(self, recommendation_engine):
        """Test ranking empty candidate list."""
        ranked = await recommendation_engine._rank_candidates([], "user123", Persona.COMFORT)
        assert ranked == []

    @pytest.mark.asyncio
    async def test_rank_candidates_sorting(self, recommendation_engine):
        """Test candidates are sorted by score."""
        route1 = Mock(spec=Route)
        route1.journey_id = "r1"
        route1.segments = [Mock(departure_time=datetime.now().replace(hour=8))]
        route1.total_cost = 2000
        route1.transfers = []
        route1.availability_probability = 0.9
        route1.reliability_score = 0.85
        route1.metadata = {}

        route2 = Mock(spec=Route)
        route2.journey_id = "r2"
        route2.segments = [Mock(departure_time=datetime.now().replace(hour=20))]
        route2.total_cost = 8000
        route2.transfers = [Mock(), Mock()]
        route2.availability_probability = 0.3
        route2.reliability_score = 0.5
        route2.metadata = {}

        candidates = [route1, route2]

        # Mock user preferences to avoid iteration issues
        recommendation_engine._get_user_preferences = Mock(return_value={
            "preferred_hours": [8, 9]
        })

        ranked = await recommendation_engine._rank_candidates(
            candidates, "user123", Persona.COMFORT
        )

        # Better route should be first (higher confidence score)
        assert len(ranked) == 2
        # Route 1 should have higher score than route 2
        score1 = ranked[0].metadata.get("recommendation_score", 0)
        score2 = ranked[1].metadata.get("recommendation_score", 0) if len(ranked) > 1 else 0
        assert score1 >= score2


class TestResponseFormatting:
    """Test response formatting."""

    def test_format_response_empty(self, recommendation_engine):
        """Test formatting empty recommendations."""
        response = recommendation_engine._format_response([], "test", Persona.COMFORT)

        assert response["recommendations"] == []
        assert "generated_at" in response["metadata"]
        assert response["metadata"]["algorithm_version"] == "1.0"

    def test_format_response_with_recommendations(self, recommendation_engine, mock_route):
        """Test formatting recommendations."""
        response = recommendation_engine._format_response(
            [mock_route], "generated", Persona.COMFORT
        )

        assert len(response["recommendations"]) == 1
        assert "generated_at" in response["metadata"]
        assert len(response["reasons"]) == 1


class TestIntegration:
    """Integration tests."""

    @pytest.mark.asyncio
    async def test_get_recommendations_flow(self, recommendation_engine, mock_route):
        """Test full recommendation flow."""
        # Mock the candidate generation to return test route
        mock_route.to_dict = Mock(return_value={
            "journey_id": "route_123",
            "legs": [],
            "total_cost": 2500.0,
            "num_transfers": 0
        })

        recommendation_engine._generate_candidates = AsyncMock(return_value=[mock_route])
        recommendation_engine._rank_candidates = AsyncMock(return_value=[mock_route])

        result = await recommendation_engine.get_recommendations(
            user_id="test_user",
            source="NDLS",
            destination="BCT",
            travel_date="2026-06-10",
            persona=Persona.COMFORT,
            limit=10
        )

        assert "recommendations" in result or "status" in result
        assert "metadata" in result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
