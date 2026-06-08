"""
Storage Layer for Synthetic Data Generation.

This module provides storage solutions for synthetic data:
- Feature Store for ML training
- Route Graph for route generation
- PostgreSQL for relational data
- Redis for caching
"""

import redis
import psycopg2
from psycopg2 import sql
from typing import Dict, List, Any, Optional
from dataclasses import dataclass
import json
import pickle
import hashlib


@dataclass
class Route:
    """Represents a route in the route graph."""
    route_id: str
    from_station: str
    to_station: str
    segments: List[Dict[str, Any]]
    total_fare: float
    total_duration: str
    transfers: int
    ml_score: float


class FeatureStore:
    """
    Feature Store for ML training with synthetic data.
    
    Provides storage and retrieval of features for ML models.
    Uses Redis for fast access and PostgreSQL for persistence.
    """
    
    def __init__(
        self,
        redis_url: str = 'redis://localhost:6379',
        postgres_url: str = 'postgresql://localhost:5432/synthetic_data'
    ):
        """
        Initialize the feature store.
        
        Args:
            redis_url: Redis connection URL
            postgres_url: PostgreSQL connection URL
        """
        self.redis_url = redis_url
        self.postgres_url = postgres_url
        self.redis_client = redis.from_url(redis_url)
        self.postgres_conn = psycopg2.connect(postgres_url)
    
    def store_features(
        self,
        feature_name: str,
        features: Dict[str, Any],
        ttl: int = 3600
    ) -> bool:
        """
        Store features in Redis.
        
        Args:
            feature_name: Name of the feature set
            features: Feature dictionary
            ttl: Time to live in seconds
            
        Returns:
            True if successful, False otherwise
        """
        try:
            key = f"features:{feature_name}"
            self.redis_client.setex(
                key,
                ttl,
                json.dumps(features)
            )
            return True
        except Exception as e:
            print(f"Error storing features: {e}")
            return False
    
    def get_features(self, feature_name: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve features from Redis.
        
        Args:
            feature_name: Name of the feature set
            
        Returns:
            Feature dictionary or None if not found
        """
        try:
            key = f"features:{feature_name}"
            data = self.redis_client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            print(f"Error retrieving features: {e}")
            return None
    
    def store_training_data(
        self,
        dataset_name: str,
        features: List[Dict[str, Any]],
        labels: List[Any]
    ) -> bool:
        """
        Store training data in PostgreSQL.
        
        Args:
            dataset_name: Name of the dataset
            features: List of feature dictionaries
            labels: List of labels
            
        Returns:
            True if successful, False otherwise
        """
        try:
            cursor = self.postgres_conn.cursor()
            
            # Create table if not exists
            cursor.execute(sql.SQL("""
                CREATE TABLE IF NOT EXISTS {} (
                    id SERIAL PRIMARY KEY,
                    dataset_name VARCHAR(100),
                    features JSONB,
                    label JSONB,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """).format(sql.Identifier(f"training_data_{dataset_name}")))
            
            # Insert data
            for features_dict, label in zip(features, labels):
                cursor.execute(sql.SQL("""
                    INSERT INTO {} (dataset_name, features, label)
                    VALUES (%s, %s, %s)
                """).format(sql.Identifier(f"training_data_{dataset_name}")), (
                    dataset_name,
                    json.dumps(features_dict),
                    json.dumps(label)
                ))
            
            self.postgres_conn.commit()
            cursor.close()
            return True
        except Exception as e:
            print(f"Error storing training data: {e}")
            return False
    
    def get_training_data(self, dataset_name: str) -> Optional[List[Dict[str, Any]]]:
        """
        Retrieve training data from PostgreSQL.
        
        Args:
            dataset_name: Name of the dataset
            
        Returns:
            List of training records or None if not found
        """
        try:
            cursor = self.postgres_conn.cursor()
            cursor.execute(sql.SQL("""
                SELECT id, dataset_name, features, label
                FROM {}
                WHERE dataset_name = %s
            """).format(sql.Identifier(f"training_data_{dataset_name}")), (dataset_name,))
            
            rows = cursor.fetchall()
            cursor.close()
            
            return [
                {
                    'id': row[0],
                    'dataset_name': row[1],
                    'features': row[2],
                    'label': row[3]
                }
                for row in rows
            ]
        except Exception as e:
            print(f"Error retrieving training data: {e}")
            return None
    
    def close(self):
        """Close database connections."""
        self.redis_client.close()
        self.postgres_conn.close()


class RouteGraph:
    """
    Route Graph for efficient route generation.
    
    Stores train schedules as a graph for fast route queries.
    Uses PostgreSQL for persistence and Redis for caching.
    """
    
    def __init__(
        self,
        redis_url: str = 'redis://localhost:6379',
        postgres_url: str = 'postgresql://localhost:5432/synthetic_data'
    ):
        """
        Initialize the route graph.
        
        Args:
            redis_url: Redis connection URL
            postgres_url: PostgreSQL connection URL
        """
        self.redis_url = redis_url
        self.postgres_url = postgres_url
        self.redis_client = redis.from_url(redis_url)
        self.postgres_conn = psycopg2.connect(postgres_url)
    
    def add_station(self, station_code: str, station_data: Dict[str, Any]) -> bool:
        """
        Add a station to the graph.
        
        Args:
            station_code: Station code
            station_data: Station data dictionary
            
        Returns:
            True if successful, False otherwise
        """
        try:
            key = f"stations:{station_code}"
            self.redis_client.setex(
                key,
                86400,  # 24 hours TTL
                json.dumps(station_data)
            )
            return True
        except Exception as e:
            print(f"Error adding station: {e}")
            return False
    
    def get_station(self, station_code: str) -> Optional[Dict[str, Any]]:
        """
        Get station data from cache.
        
        Args:
            station_code: Station code
            
        Returns:
            Station data dictionary or None if not found
        """
        try:
            key = f"stations:{station_code}"
            data = self.redis_client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            print(f"Error getting station: {e}")
            return None
    
    def add_schedule(self, schedule: Dict[str, Any]) -> bool:
        """
        Add a train schedule to the graph.
        
        Args:
            schedule: Schedule dictionary
            
        Returns:
            True if successful, False otherwise
        """
        try:
            # Add to Redis
            train_number = schedule['train_number']
            key = f"schedules:{train_number}"
            self.redis_client.setex(
                key,
                86400,  # 24 hours TTL
                json.dumps(schedule)
            )
            
            # Add to adjacency list (from_station -> to_stations)
            from_station = schedule['from_station']
            to_station = schedule['to_station']
            
            adjacency_key = f"adjacency:{from_station}"
            self.redis_client.sadd(adjacency_key, to_station)
            
            return True
        except Exception as e:
            print(f"Error adding schedule: {e}")
            return False
    
    def get_schedule(self, train_number: str) -> Optional[Dict[str, Any]]:
        """
        Get train schedule from cache.
        
        Args:
            train_number: Train number
            
        Returns:
            Schedule dictionary or None if not found
        """
        try:
            key = f"schedules:{train_number}"
            data = self.redis_client.get(key)
            if data:
                return json.loads(data)
            return None
        except Exception as e:
            print(f"Error getting schedule: {e}")
            return None
    
    def get_connections(self, station_code: str) -> List[str]:
        """
        Get all stations reachable from a station.
        
        Args:
            station_code: Station code
            
        Returns:
            List of reachable station codes
        """
        try:
            key = f"adjacency:{station_code}"
            connections = self.redis_client.smembers(key)
            return [c.decode('utf-8') for c in connections]
        except Exception as e:
            print(f"Error getting connections: {e}")
            return []
    
    def generate_route(
        self,
        from_station: str,
        to_station: str,
        max_transfers: int = 2
    ) -> List[Route]:
        """
        Generate routes between stations using BFS.
        
        Args:
            from_station: Origin station code
            to_station: Destination station code
            max_transfers: Maximum number of transfers
            
        Returns:
            List of Route objects
        """
        routes = []
        
        # BFS to find routes
        queue = [(from_station, [from_station], 0)]
        visited = set()
        
        while queue:
            current_station, path, transfers = queue.pop(0)
            
            if current_station in visited:
                continue
            
            visited.add(current_station)
            
            if current_station == to_station:
                # Found a route
                route = self._build_route(path)
                routes.append(route)
                continue
            
            if transfers >= max_transfers:
                continue
            
            # Get connections
            connections = self.get_connections(current_station)
            
            for connection in connections:
                if connection not in visited:
                    queue.append((connection, path + [connection], transfers))
        
        return routes
    
    def _build_route(self, path: List[str]) -> Route:
        """
        Build a Route object from a path.
        
        Args:
            path: List of station codes
            
        Returns:
            Route object
        """
        # This is a simplified implementation
        # In production, would need to look up actual train schedules
        
        segments = []
        for i in range(len(path) - 1):
            segment = {
                'from_station': path[i],
                'to_station': path[i + 1],
                'train_number': f'TRAIN-{i}',
                'departure_time': f'{8 + i}:00',
                'arrival_time': f'{10 + i}:00',
                'duration': '2h',
            }
            segments.append(segment)
        
        return Route(
            route_id=f"route-{hashlib.md5(str(path).encode()).hexdigest()[:8]}",
            from_station=path[0],
            to_station=path[-1],
            segments=segments,
            total_fare=1000,
            total_duration=f"{2 * len(segments)}h",
            transfers=len(segments) - 1,
            ml_score=0.85,
        )
    
    def close(self):
        """Close database connections."""
        self.redis_client.close()
        self.postgres_conn.close()


# Convenience functions for storage
def create_feature_store(
    redis_url: str = 'redis://localhost:6379',
    postgres_url: str = 'postgresql://localhost:5432/synthetic_data'
) -> FeatureStore:
    """
    Create a feature store instance.
    
    Args:
        redis_url: Redis connection URL
        postgres_url: PostgreSQL connection URL
        
    Returns:
        FeatureStore instance
    """
    return FeatureStore(redis_url, postgres_url)


def create_route_graph(
    redis_url: str = 'redis://localhost:6379',
    postgres_url: str = 'postgresql://localhost:5432/synthetic_data'
) -> RouteGraph:
    """
    Create a route graph instance.
    
    Args:
        redis_url: Redis connection URL
        postgres_url: PostgreSQL connection URL
        
    Returns:
        RouteGraph instance
    """
    return RouteGraph(redis_url, postgres_url)