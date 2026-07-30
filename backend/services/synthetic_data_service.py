"""
Synthetic Data Service for cost-free route generation.

This service integrates all synthetic data generation components:
- Train schedule generation
- Fare data generation
- Availability data generation
- User behavior generation
- Data validation
- Storage integration
"""

from typing import Dict, List, Any, Optional
from datetime import datetime
import logging

from .synthetic_data.generators import (
    TrainScheduleGenerator,
    FareGenerator,
    AvailabilityGenerator,
    UserBehaviorGenerator,
    generate_train_schedules,
    generate_fares,
    generate_availability,
    generate_user_behavior,
)

from .synthetic_data.validation import (
    DistributionValidator,
    StatisticalValidator,
    RealismScorer,
    validate_synthetic_data,
)

from .synthetic_data.storage import (
    FeatureStore,
    RouteGraph,
    create_feature_store,
    create_route_graph,
)

logger = logging.getLogger(__name__)


class SyntheticDataService:
    """
    Main service for synthetic data generation and management.
    
    Provides high-level API for:
    - Generating synthetic data
    - Validating data quality
    - Storing data for ML training
    - Integrating with route generation
    """
    
    def __init__(
        self,
        redis_url: str = 'redis://localhost:6379',
        postgres_url: str = 'postgresql://localhost:5432/synthetic_data'
    ):
        """
        Initialize the synthetic data service.
        
        Args:
            redis_url: Redis connection URL
            postgres_url: PostgreSQL connection URL
        """
        self.redis_url = redis_url
        self.postgres_url = postgres_url
        
        # Initialize generators
        self.schedule_generator = TrainScheduleGenerator()
        self.fare_generator = FareGenerator(self.schedule_generator)
        self.availability_generator = AvailabilityGenerator(self.schedule_generator)
        self.user_behavior_generator = UserBehaviorGenerator()
        
        # Initialize storage
        self.feature_store = create_feature_store(redis_url, postgres_url)
        self.route_graph = create_route_graph(redis_url, postgres_url)
        
        logger.info("SyntheticDataService initialized")
    
    def generate_all_data(self, counts: Dict[str, int] = None) -> Dict[str, Any]:
        """
        Generate all synthetic data.
        
        Args:
            counts: Dictionary with counts for each data type
                    Default: schedules=1M, fares=2M, availability=10M, behavior=5M
            
        Returns:
            Dictionary with generation results
        """
        if counts is None:
            counts = {
                'schedules': 1000000,
                'fares': 2000000,
                'availability': 10000000,
                'behavior': 5000000,
            }
        
        results = {}
        
        # Generate train schedules
        logger.info(f"Generating {counts['schedules']} train schedules...")
        start_time = datetime.now()
        schedules = generate_train_schedules(counts['schedules'])
        schedule_time = (datetime.now() - start_time).total_seconds()
        results['schedules'] = {
            'count': len(schedules),
            'time_seconds': schedule_time,
        }
        logger.info(f"Generated {len(schedules)} schedules in {schedule_time:.2f}s")
        
        # Generate fares
        logger.info(f"Generating {counts['fares']} fare records...")
        start_time = datetime.now()
        fares = generate_fares(counts['fares'])
        fare_time = (datetime.now() - start_time).total_seconds()
        results['fares'] = {
            'count': len(fares),
            'time_seconds': fare_time,
        }
        logger.info(f"Generated {len(fares)} fares in {fare_time:.2f}s")
        
        # Generate availability
        logger.info(f"Generating {counts['availability']} availability records...")
        start_time = datetime.now()
        availability = generate_availability(counts['availability'])
        availability_time = (datetime.now() - start_time).total_seconds()
        results['availability'] = {
            'count': len(availability),
            'time_seconds': availability_time,
        }
        logger.info(f"Generated {len(availability)} availability records in {availability_time:.2f}s")
        
        # Generate user behavior
        logger.info(f"Generating {counts['behavior']} user behavior records...")
        start_time = datetime.now()
        behavior = generate_user_behavior(counts['behavior'])
        behavior_time = (datetime.now() - start_time).total_seconds()
        results['behavior'] = {
            'count': len(behavior),
            'time_seconds': behavior_time,
        }
        logger.info(f"Generated {len(behavior)} user behavior records in {behavior_time:.2f}s")
        
        return results
    
    def validate_data(self, real_data_path: str, synthetic_data_path: str) -> Dict[str, Any]:
        """
        Validate synthetic data against real data.
        
        Args:
            real_data_path: Path to real data CSV
            synthetic_data_path: Path to synthetic data CSV
            
        Returns:
            Dictionary with validation results
        """
        import pandas as pd
        
        # Load data
        real_data = pd.read_csv(real_data_path)
        synthetic_data = pd.read_csv(synthetic_data_path)
        
        # Validate
        results = validate_synthetic_data(real_data, synthetic_data)
        
        return results
    
    def store_data(self, data_type: str, data: List[Any]) -> bool:
        """
        Store synthetic data in feature store.
        
        Args:
            data_type: Type of data ('schedules', 'fares', 'availability', 'behavior')
            data: List of data records
            
        Returns:
            True if successful, False otherwise
        """
        try:
            if data_type == 'schedules':
                for schedule in data:
                    self.route_graph.add_schedule(schedule.__dict__)
            
            elif data_type == 'fares':
                for fare in data:
                    self.feature_store.store_features(
                        f"fare:{fare.train_number}:{fare.travel_date}",
                        fare.__dict__
                    )
            
            elif data_type == 'availability':
                for avail in data:
                    self.feature_store.store_features(
                        f"availability:{avail.train_number}:{avail.travel_date}:{avail.travel_class}",
                        avail.__dict__
                    )
            
            elif data_type == 'behavior':
                for behavior in data:
                    self.feature_store.store_features(
                        f"behavior:{behavior.user_id}:{behavior.session_id}",
                        behavior.__dict__
                    )
            
            return True
        except Exception as e:
            logger.error(f"Error storing data: {e}")
            return False
    
    def get_routes(
        self,
        from_station: str,
        to_station: str,
        travel_date: str,
        max_transfers: int = 2
    ) -> List[Dict[str, Any]]:
        """
        Get routes between stations using synthetic data.
        
        Args:
            from_station: Origin station code
            to_station: Destination station code
            travel_date: Travel date (YYYY-MM-DD)
            max_transfers: Maximum number of transfers
            
        Returns:
            List of route dictionaries
        """
        routes = []
        
        # Generate routes using route graph
        route_objects = self.route_graph.generate_route(
            from_station, to_station, max_transfers
        )
        
        for route in route_objects:
            route_dict = {
                'route_id': route.route_id,
                'from_station': route.from_station,
                'to_station': route.to_station,
                'segments': route.segments,
                'total_fare': route.total_fare,
                'total_duration': route.total_duration,
                'transfers': route.transfers,
                'ml_score': route.ml_score,
            }
            routes.append(route_dict)
        
        return routes
    
    def get_availability(
        self,
        train_number: str,
        travel_date: str,
        travel_class: str
    ) -> Optional[Dict[str, Any]]:
        """
        Get availability for a train.
        
        Args:
            train_number: Train number
            travel_date: Travel date (YYYY-MM-DD)
            travel_class: Travel class
            
        Returns:
            Availability dictionary or None if not found
        """
        key = f"availability:{train_number}:{travel_date}:{travel_class}"
        return self.feature_store.get_features(key)
    
    def close(self):
        """Close database connections."""
        self.feature_store.close()
        self.route_graph.close()


# Global instance
_synthetic_data_service: Optional[SyntheticDataService] = None


def get_synthetic_data_service() -> SyntheticDataService:
    """
    Get or create the global synthetic data service instance.
    
    Returns:
        SyntheticDataService instance
    """
    global _synthetic_data_service
    
    if _synthetic_data_service is None:
        _synthetic_data_service = SyntheticDataService()
    
    return _synthetic_data_service


def create_synthetic_data_service(
    redis_url: str = 'redis://localhost:6379',
    postgres_url: str = 'postgresql://localhost:5432/synthetic_data'
) -> SyntheticDataService:
    """
    Create a new synthetic data service instance.
    
    Args:
        redis_url: Redis connection URL
        postgres_url: PostgreSQL connection URL
        
    Returns:
        SyntheticDataService instance
    """
    return SyntheticDataService(redis_url, postgres_url)