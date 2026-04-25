from sqlalchemy.orm import Session
from typing import Optional, Dict, Any, List
from datetime import datetime, timedelta
import logging
import hashlib
import asyncio
from collections import deque, defaultdict
from dataclasses import dataclass, field

from database.models import User, Profile, Booking, SearchEvent
from schemas import UserCreate
from utils.security import get_password_hash, verify_password
from core.resilience import circuit_breaker_manager, CircuitBreaker, CircuitConfig
from core.retry import RetryPolicy

logger = logging.getLogger(__name__)


@dataclass
class TravelPattern:
    """User travel pattern analysis."""
    user_id: str
    most_frequent_routes: List[tuple] = field(default_factory=list)  # [(source, dest), ...]
    preferred_times: List[int] = field(default_factory=list)  # Hours of day
    preferred_days: List[int] = field(default_factory=list)  # Day of week
    avg_booking_advance_days: float = 7.0
    preferred_class: str = "SL"
    price_sensitivity: float = 0.5
    flexibility_score: float = 0.5
    total_trips: int = 0
    last_travel_date: Optional[datetime] = None


class UserServiceMetrics:
    """Metrics tracking for user service."""
    
    def __init__(self):
        self._metrics: deque = deque(maxlen=500)
        self._metrics_lock = asyncio.Lock()
    
    async def record_operation(self, operation: str, success: bool, duration_ms: float):
        """Record user service operation metrics."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "operation": operation,
                "success": success,
                "duration_ms": duration_ms
            })
    
    def get_metrics(self) -> dict:
        """Get service metrics."""
        if not self._metrics:
            return {"total_operations": 0, "success_rate": 0.0}
        
        total = len(self._metrics)
        successful = sum(1 for m in self._metrics if m["success"])
        by_operation = {}
        for m in self._metrics:
            op = m["operation"]
            if op not in by_operation:
                by_operation[op] = {"total": 0, "success": 0}
            by_operation[op]["total"] += 1
            if m["success"]:
                by_operation[op]["success"] += 1
        
        return {
            "total_operations": total,
            "successful_operations": successful,
            "failed_operations": total - successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "by_operation": by_operation
        }


class UserService:
    """User management service with caching, validation, and knowledge integration."""

    def __init__(self, db: Session, knowledge_graph=None, redistribution_service=None):
        self.db = db
        self.kg = knowledge_graph  # Knowledge Graph integration
        self.redistribution = redistribution_service  # Demand Redistribution integration
        
        # Cache management
        self._cache: Dict[str, Dict] = {}
        self._cache_ttl_seconds = 300  # 5 minutes
        
        # Circuit breaker for database operations
        self._db_breaker = circuit_breaker_manager.get_or_create(
            "user_service_db",
            CircuitConfig(failure_threshold=5, timeout_seconds=30.0, success_threshold=2)
        )
        
        # Retry policy for database operations
        self._db_retry = RetryPolicy(
            max_attempts=3,
            initial_delay=0.5,
            max_delay=5.0,
            conditions=[
                lambda e: "connection" in str(e).lower(),
                lambda e: "timeout" in str(e).lower()
            ]
        )
        
        # Metrics tracking
        self._metrics = UserServiceMetrics()
        
        logger.info("UserService initialized with resilience patterns and service integrations")

    def _get_cache_key(self, key_type: str, value: str) -> str:
        """Generate cache key for user lookups."""
        return f"user:{key_type}:{value}"

    def _is_cache_valid(self, cached: Dict) -> bool:
        """Check if cached user data is still valid."""
        if not cached:
            return False
        cached_time = cached.get("_cached_at", 0)
        return (datetime.utcnow().timestamp() - cached_time) < self._cache_ttl_seconds

    def get_user_by_email(self, email: str) -> Optional[User]:
        """
        Task 6.3: Cached user lookup by email.
        """
        cache_key = self._get_cache_key("email", email.lower())
        
        # Check cache first
        if cache_key in self._cache and self._is_cache_valid(self._cache[cache_key]):
            cached = self._cache[cache_key]
            logger.debug(f"📦 Cache hit for user email {email}")
            # Return user from cache by fetching from DB with cached ID
            if cached.get("user_id"):
                return self.db.query(User).filter(User.id == cached["user_id"]).first()
        
        # Perform DB query
        user = self.db.query(User).filter(User.email == email.lower()).first()
        
        # Cache the result
        if user:
            self._cache[cache_key] = {
                "user_id": user.id,
                "email": user.email,
                "_cached_at": datetime.utcnow().timestamp()
            }
        
        return user

    def get_user_by_supabase_id(self, supabase_id: str) -> Optional[User]:
        """
        Task 6.2: Cached user lookup by Supabase ID.
        """
        cache_key = self._get_cache_key("supabase_id", supabase_id)
        
        # Check cache first
        if cache_key in self._cache and self._is_cache_valid(self._cache[cache_key]):
            cached = self._cache[cache_key]
            if cached.get("user_id"):
                return self.db.query(User).filter(User.id == cached["user_id"]).first()
        
        # Perform DB query
        user = self.db.query(User).filter(User.supabase_id == supabase_id).first()
        
        # Cache the result
        if user:
            self._cache[cache_key] = {
                "user_id": user.id,
                "supabase_id": supabase_id,
                "_cached_at": datetime.utcnow().timestamp()
            }
        
        return user

    def get_user_by_id(self, user_id: str) -> Optional[User]:
        """Get user by ID with caching."""
        cache_key = self._get_cache_key("id", user_id)
        
        if cache_key in self._cache and self._is_cache_valid(self._cache[cache_key]):
            cached = self._cache[cache_key]
            if cached.get("user_data"):
                return User(**cached["user_data"])
        
        user = self.db.query(User).filter(User.id == user_id).first()
        
        if user:
            self._cache[cache_key] = {
                "user_id": user.id,
                "user_data": {
                    "id": user.id,
                    "email": user.email,
                    "role": user.role,
                    "is_verified": user.is_verified
                },
                "_cached_at": datetime.utcnow().timestamp()
            }
        
        return user

    def create_user(self, user_create: UserCreate) -> User:
        """
        Create a new user with validation.
        """
        # Check if user already exists
        existing = self.get_user_by_email(user_create.email)
        if existing:
            raise ValueError(f"User with email {user_create.email} already exists")
        
        # Validate password strength
        if len(user_create.password) < 8:
            raise ValueError("Password must be at least 8 characters long")
        
        hashed_password = get_password_hash(user_create.password)
        
        db_user = User(
            email=user_create.email,
            password_hash=hashed_password,
            phone_number=user_create.phone_number,
        )
        
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        
        # Invalidate email cache
        self._invalidate_email_cache(user_create.email)
        
        logger.info(f"✅ User created: {db_user.id}")
        return db_user

    def create_user_with_data(self, data: dict) -> User:
        """
        Helper to create a user from a generic data dictionary. This is useful
        for Supabase/OTP flows where we may only have phone or email.
        """
        supabase_id = data.get("supabase_id")
        email = data.get("email")
        
        # Check if user already exists
        if supabase_id:
            existing = self.get_user_by_supabase_id(supabase_id)
            if existing:
                logger.info(f"User already exists with supabase_id: {supabase_id}")
                return existing
        
        if email:
            existing = self.get_user_by_email(email)
            if existing:
                logger.info(f"User already exists with email: {email}")
                return existing
        
        # Support both naming conventions
        full_name = data.get("full_name") or data.get("name")
        role = data.get("role", "user")
        
        user_data = {
            "email": email,
            "supabase_id": supabase_id,
            "role": role,
            "full_name": full_name,
            "is_verified": data.get("is_verified", False),
            "phone_number": data.get("phone_number")
        }
        
        # Create profile if supabase_id provided
        if supabase_id:
            existing_profile = self.db.query(Profile).filter(Profile.id == supabase_id).first()
            if not existing_profile:
                profile = Profile(
                    id=supabase_id, 
                    name=full_name, 
                    phone=data.get("phone_number")
                )
                self.db.add(profile)

        db_user = User(**user_data)
        self.db.add(db_user)
        self.db.commit()
        self.db.refresh(db_user)
        
        # Invalidate caches
        if email:
            self._invalidate_email_cache(email)
        if supabase_id:
            self._invalidate_supabase_cache(supabase_id)
        
        logger.info(f"✅ User created from data: {db_user.id}")
        return db_user

    def _invalidate_email_cache(self, email: str) -> None:
        """Invalidate cache for an email."""
        cache_key = self._get_cache_key("email", email.lower())
        self._cache.pop(cache_key, None)

    def _invalidate_supabase_cache(self, supabase_id: str) -> None:
        """Invalidate cache for a supabase ID."""
        cache_key = self._get_cache_key("supabase_id", supabase_id)
        self._cache.pop(cache_key, None)

    def authenticate_user(
        self, email: str, password: str
    ) -> Optional[User]:
        """
        Authenticate a user by email and password.
        """
        user = self.get_user_by_email(email)
        if not user:
            logger.warning(f"Authentication failed: user not found for email {email}")
            return None
        
        if not verify_password(password, user.password_hash):
            logger.warning(f"Authentication failed: invalid password for {email}")
            return None
        
        logger.info(f"✅ User authenticated: {user.id}")
        return user

    def update_user_profile(self, user: User, changes: dict) -> User:
        """
        Apply profile changes to both User and Profile tables.
        """
        # Validate changes
        if not changes:
            return user
        
        # Separate fields for User and Profile tables
        profile_fields = {}
        user_fields = {}
        
        for k, v in changes.items():
            if k in ("name", "phone", "gender", "emergency_contact"):
                profile_fields[k] = v
            elif k in ("email", "phone_number", "full_name"):
                user_fields[k] = v
        
        # Update user fields
        if user_fields:
            for k, v in user_fields.items():
                setattr(user, k, v)
            self._invalidate_email_cache(user.email)
        
        # Update profile fields
        if profile_fields:
            # Ensure profile row exists
            if not hasattr(user, 'profile') or not user.profile:
                prof = Profile(id=user.id, **profile_fields)
                self.db.add(prof)
                self.db.flush()
            else:
                for k, v in profile_fields.items():
                    setattr(user.profile, k, v)
        
        self.db.commit()
        self.db.refresh(user)
        
        # Invalidate caches
        self._invalidate_email_cache(user.email)
        if user.supabase_id:
            self._invalidate_supabase_cache(user.supabase_id)
        
        logger.info(f"✅ User profile updated: {user.id}")
        return user

    def update_user_location(self, user: User, latitude: float, longitude: float) -> User:
        """
        Record the current location in LiveLocation table.
        """
        from database.models import LiveLocation
        
        # Validate coordinates
        if not (-90 <= latitude <= 90):
            raise ValueError("Invalid latitude value")
        if not (-180 <= longitude <= 180):
            raise ValueError("Invalid longitude value")
        
        loc = LiveLocation(
            user_id=user.id, 
            latitude=latitude, 
            longitude=longitude
        )
        self.db.add(loc)
        self.db.commit()
        self.db.refresh(user)
        
        logger.debug(f"📍 Location updated for user {user.id}")
        return user

    def deactivate_user(self, user_id: str) -> bool:
        """
        Soft delete a user by setting is_active to False.
        """
        user = self.db.query(User).filter(User.id == user_id).first()
        if not user:
            return False
        
        user.is_active = False
        self.db.commit()
        
        # Invalidate all caches for this user
        self._invalidate_email_cache(user.email)
        if user.supabase_id:
            self._invalidate_supabase_cache(user.supabase_id)
        
        logger.info(f"❌ User deactivated: {user_id}")
        return True

    def clear_cache(self) -> None:
        """Clear all user caches."""
        self._cache.clear()
        logger.info("User cache cleared")

    def get_cache_stats(self) -> Dict[str, Any]:
        """Get cache statistics."""
        return {
            "cache_size": len(self._cache),
            "ttl_seconds": self._cache_ttl_seconds
        }
    
    # =========================================================================
    # TRAVEL PATTERN ANALYSIS
    # =========================================================================
    
    def analyze_travel_patterns(self, user_id: str) -> TravelPattern:
        """
        Analyze user's travel patterns from booking history.
        
        Returns a TravelPattern with:
        - Most frequent routes
        - Preferred travel times
        - Preferred days
        - Booking behavior
        """
        pattern = TravelPattern(user_id=user_id)
        
        if not self.db:
            return pattern
        
        try:
            # Get user's bookings
            bookings = self.db.query(Booking).filter(
                Booking.user_id == user_id,
                Booking.booking_status == "confirmed"
            ).order_by(Booking.travel_date.desc()).limit(50).all()
            
            if not bookings:
                return pattern
            
            pattern.total_trips = len(bookings)
            pattern.last_travel_date = bookings[0].travel_date if bookings else None
            
            # Analyze routes
            route_counts: Dict[str, int] = defaultdict(int)
            for booking in bookings:
                route_key = (booking.source_station, booking.destination_station)
                route_counts[route_key] += 1
            
            # Get top routes
            sorted_routes = sorted(route_counts.items(), key=lambda x: x[1], reverse=True)
            pattern.most_frequent_routes = [r[0] for r in sorted_routes[:5]]
            
            # Analyze times
            departure_hours: Dict[int, int] = defaultdict(int)
            departure_days: Dict[int, int] = defaultdict(int)
            advance_days: List[int] = []
            
            for booking in bookings:
                if hasattr(booking, 'departure_time') and booking.departure_time:
                    departure_hours[booking.departure_time.hour] += 1
                
                departure_days[booking.travel_date.weekday()] += 1
                
                if hasattr(booking, 'booking_date'):
                    advance = (booking.travel_date - booking.booking_date).days
                    advance_days.append(advance)
            
            # Get preferred times (top 3 hours)
            sorted_hours = sorted(departure_hours.items(), key=lambda x: x[1], reverse=True)
            pattern.preferred_times = [h[0] for h in sorted_hours[:3]]
            
            # Get preferred days (top 3 days)
            sorted_days = sorted(departure_days.items(), key=lambda x: x[1], reverse=True)
            pattern.preferred_days = [d[0] for d in sorted_days[:3]]
            
            # Calculate average booking advance
            if advance_days:
                pattern.avg_booking_advance_days = sum(advance_days) / len(advance_days)
            
            # Analyze class preferences
            class_counts: Dict[str, int] = defaultdict(int)
            for booking in bookings:
                if hasattr(booking, 'booking_class') and booking.booking_class:
                    class_counts[booking.booking_class] += 1
            
            if class_counts:
                pattern.preferred_class = max(class_counts.items(), key=lambda x: x[1])[0]
            
            # Calculate price sensitivity (based on booking timing and class)
            # Early bookers with lower classes = more price sensitive
            if pattern.avg_booking_advance_days > 14 and pattern.preferred_class in ['SL', '2S']:
                pattern.price_sensitivity = 0.8
            elif pattern.avg_booking_advance_days < 3 or pattern.preferred_class in ['1A', '2A']:
                pattern.price_sensitivity = 0.3
            
            # Calculate flexibility score
            # Multiple routes, various times = more flexible
            pattern.flexibility_score = min(1.0, (
                len(pattern.most_frequent_routes) * 0.1 +
                len(pattern.preferred_times) * 0.1 +
                len(pattern.preferred_days) * 0.1 +
                0.5
            ))
            
            logger.info(f"📊 Travel pattern analyzed for user {user_id}: {pattern.total_trips} trips")
            
        except Exception as e:
            logger.error(f"Error analyzing travel patterns for user {user_id}: {e}")
        
        return pattern
    
    async def get_travel_recommendations(self, user_id: str) -> Dict[str, Any]:
        """
        Generate travel recommendations based on user patterns.
        Integrates with Knowledge Graph for collaborative filtering.
        """
        pattern = self.analyze_travel_patterns(user_id)
        
        if pattern.total_trips == 0:
            return {
                "status": "insufficient_data",
                "message": "No travel history to generate recommendations"
            }
        
        # Generate recommendations
        recommendations = {
            "status": "success",
            "travel_pattern": {
                "total_trips": pattern.total_trips,
                "preferred_class": pattern.preferred_class,
                "avg_booking_advance_days": round(pattern.avg_booking_advance_days, 1),
                "price_sensitivity": pattern.price_sensitivity,
                "flexibility_score": pattern.flexibility_score
            },
            "recommendations": []
        }
        
        # Recommend booking timing
        if pattern.avg_booking_advance_days > 20:
            recommendations["recommendations"].append({
                "type": "booking_timing",
                "message": "You typically book well in advance. Consider setting alerts for early bird deals.",
                "action": "Enable price alerts"
            })
        elif pattern.avg_booking_advance_days < 5:
            recommendations["recommendations"].append({
                "type": "booking_timing",
                "message": "You often book last minute. Consider checking Tatkal or premium tickets.",
                "action": "Explore Tatkal booking"
            })
        
        # Recommend class upgrades
        if pattern.preferred_class in ['SL', '2S'] and pattern.total_trips > 5:
            recommendations["recommendations"].append({
                "type": "class_upgrade",
                "message": f"You frequently travel in {pattern.preferred_class}. Consider AC classes for longer journeys.",
                "action": "Explore AC class options"
            })
        
        # Recommend flexible dates
        if len(pattern.preferred_days) < 3:
            recommendations["recommendations"].append({
                "type": "flexibility",
                "message": "You have consistent travel days. Consider exploring nearby dates for better prices.",
                "action": "Check flexible date options"
            })
        
        # [INTEGRATION] Get Knowledge Graph recommendations
        if self.kg:
            try:
                kg_recommendations = await self.kg.get_personalized_recommendations(
                    user_id,
                    {
                        "preferred_routes": pattern.most_frequent_routes,
                        "preferred_times": pattern.preferred_times,
                        "preferred_class": pattern.preferred_class
                    }
                )
                if kg_recommendations:
                    recommendations["knowledge_graph_recommendations"] = kg_recommendations
            except Exception as e:
                logger.error(f"Error getting KG recommendations: {e}")
        
        return recommendations
    
    # =========================================================================
    # KNOWLEDGE GRAPH INTEGRATION
    # =========================================================================
    
    async def sync_user_to_knowledge_graph(self, user_id: str) -> bool:
        """
        Sync user data to Knowledge Graph for collaborative filtering.
        """
        if not self.kg:
            return False
        
        try:
            # Get user preferences
            pattern = self.analyze_travel_patterns(user_id)
            
            # Create/update user preference in knowledge graph
            self.kg.create_user_preference(
                user_id=user_id,
                preferred_class=pattern.preferred_class,
                preferred_time_morning=bool(pattern.preferred_times and min(pattern.preferred_times) < 12),
                flexibility_score=pattern.flexibility_score,
                price_sensitivity=pattern.price_sensitivity
            )
            
            # Update user behavior matrix
            for route in pattern.most_frequent_routes:
                route_key = f"{route[0]}->{route[1]}"
                await self.kg._update_user_behavior(
                    user_id, route_key, pattern.flexibility_score
                )
            
            logger.info(f"Synced user {user_id} to Knowledge Graph")
            return True
            
        except Exception as e:
            logger.error(f"Error syncing user to KG: {e}")
            return False
    
    async def get_similar_users(self, user_id: str, limit: int = 5) -> List[Dict]:
        """
        Get similar users from Knowledge Graph for collaborative recommendations.
        """
        if not self.kg:
            return []
        
        try:
            # Get user's preferences
            prefs = self.kg.user_preferences.get(user_id)
            if not prefs:
                return []
            
            # Get similar user recommendations
            similar = await self.kg._get_similar_user_recommendations(prefs, {})
            return similar[:limit]
            
        except Exception as e:
            logger.error(f"Error getting similar users: {e}")
            return []
    
    # =========================================================================
    # DEMAND REDISTRIBUTION INTEGRATION
    # =========================================================================
    
    async def get_redistribution_opportunities(self, user_id: str) -> List[Dict]:
        """
        Get personalized redistribution opportunities for the user.
        """
        if not self.redistribution:
            return []
        
        try:
            # Get user's travel patterns
            pattern = self.analyze_travel_patterns(user_id)
            
            # Get network opportunities
            opportunities = await self.redistribution.identify_opportunities()
            
            # Filter for user's preferred routes
            user_routes = set(pattern.most_frequent_routes)
            relevant_opportunities = []
            
            for opp in opportunities:
                source = (opp.source_route.source, opp.source_route.destination)
                target = (opp.target_route.source, opp.target_route.destination)
                
                if source in user_routes or target in user_routes:
                    relevant_opportunities.append({
                        "source_route": f"{opp.source_route.source}->{opp.source_route.destination}",
                        "target_route": f"{opp.target_route.source}->{opp.target_route.destination}",
                        "passengers_needed": opp.passengers_needed,
                        "incentive_range": opp.incentive_range,
                        "time_advantage": opp.time_advantage
                    })
            
            return relevant_opportunities
            
        except Exception as e:
            logger.error(f"Error getting redistribution opportunities: {e}")
            return []
    
    # =========================================================================
    # RESILIENCE PATTERNS
    # =========================================================================

    def get_metrics(self) -> dict:
        """Get service metrics."""
        return self._metrics.get_metrics()

    def health_check(self) -> dict:
        """Check service health."""
        return {
            "status": "healthy",
            "circuit_breaker": {
                "state": self._db_breaker.get_state().value,
                "failure_count": self._db_breaker.failure_count,
                "success_count": self._db_breaker.success_count
            },
            "metrics": self._metrics.get_metrics(),
            "cache_stats": self.get_cache_stats()
        }

    def reset_circuit_breaker(self):
        """Reset the circuit breaker."""
        self._db_breaker.reset()
        logger.info("Circuit breaker reset for user_service")