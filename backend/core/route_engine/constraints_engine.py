import logging
from datetime import datetime, date, timedelta
from typing import Optional, Dict, Any, List
from .constraints import RouteConstraints, Persona

logger = logging.getLogger(__name__)

class ConstraintsEngine:
    """
    Intelligent Pre-Processing Gate - Phase 4.
    Validates, Normalizes, and Pre-Filters requests before they hit the routing engines.
    """
    
    @staticmethod
    def initialize_constraints(
        persona_str: str = "comfort",
        max_transfers: Optional[int] = None,
        max_fare: Optional[float] = None,
        confirmed_only: bool = False,
        direct_only: bool = False,
        travel_date: Optional[date] = None,
        time_priority: float = 0.5,
        cost_priority: float = 0.5,
        quota: str = "GN"
    ) -> RouteConstraints:
        """
        Creates a high-performance RouteConstraints object with persona-specific weights.
        """
        # 1. Normalize Persona [Task 25.9]
        persona_map = {
            "budget": Persona.BUDGET,
            "economy": Persona.BUDGET,
            "fast": Persona.FAST,
            "emergency": Persona.EMERGENCY,
            "comfort": Persona.COMFORT,
            "premium": Persona.COMFORT,
            "family": Persona.FAMILY,
            "standard": Persona.STANDARD
        }
        
        persona = persona_map.get(persona_str.lower(), Persona.STANDARD)

        # 2. Date Validation (Task 4.4)
        if travel_date:
            max_date = date.today() + timedelta(days=120)
            if travel_date > max_date:
                logger.warning(f"Travel date {travel_date} beyond 120-day IRCTC window. Capping.")
                travel_date = max_date
            if travel_date < date.today():
                travel_date = date.today()

        # 3. Create Base Constraints
        constraints = RouteConstraints(
            persona=persona,
            time_priority=time_priority,
            cost_priority=cost_priority,
            quota=quota.upper().strip()
        )

        # 4. Apply Overrides (Task 4.6, 4.7)
        if max_transfers is not None:
            constraints.max_transfers = max_transfers
        
        if direct_only:
            constraints.max_transfers = 0
            
        # Metadata for tracking
        constraints.debug = True # Enable for audit logs
        
        # We can store custom flags in metadata or extend the dataclass
        # For now, let's ensure Persona Weights are correctly scaled
        ConstraintsEngine._apply_persona_logic(constraints, confirmed_only, max_fare)
        
        return constraints

    @staticmethod
    def _apply_persona_logic(c: RouteConstraints, confirmed_only: bool, max_fare: Optional[float]):
        """Fine-tunes weights based on specific high-level flags."""
        
        # Task 4.7: Fare Capping (Threaded into weight logic)
        if max_fare:
            # If user has a hard budget, increase cost weight significantly
            c.weights.cost *= 5.0
            
        # Task 4.1: Confirmed Only Logic
        if confirmed_only:
            # Penalize transfers even more as they increase waitlist risk
            c.weights.transfer *= 1.5
            # Increase reliability/survival weight
            c.reliability_weight = 0.9

    @staticmethod
    def normalize_station_code(code: str) -> str:
        """Standardizes station codes (e.g., 'ndls' -> 'NDLS')."""
        if not code: return ""
        return code.strip().upper()

    @staticmethod
    def get_cache_key(source: str, dest: str, travel_date: date, c: RouteConstraints) -> str:
        """Deterministic hashing for Redis hits (Task 4.9)."""
        persona_val = c.persona.value
        transfers = c.max_transfers
        quota = c.quota
        # Simple string-based key for the orchestrator
        return f"route:{source}:{dest}:{travel_date.isoformat()}:{persona_val}:t{transfers}:{quota}"
