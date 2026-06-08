"""
Knowledge Graph Persistence Layer

Persists knowledge graph to database for durability and recovery.
Enables incremental updates and version history.

Patent Innovation #2: Knowledge-Based Travel Optimization
Captures all travel-related knowledge and applies it to optimize
routing, pricing, and recommendations.
"""

import logging
import json
import pickle
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, date
from dataclasses import dataclass, asdict
# pyrefly: ignore [missing-import]
from sqlalchemy.orm import Session
# pyrefly: ignore [missing-import]
from sqlalchemy import and_

from database.models import KnowledgeGraphSnapshot, UserPreferenceModel, RoutePatternModel
from database.models.redistribution import KnowledgeGraphNode as KnowledgeGraphNodeModel, KnowledgeGraphEdge as KnowledgeGraphEdgeModel
from services.knowledge_graph_service import TravelKnowledgeGraph, StationNode, RoutePattern

logger = logging.getLogger("knowledge_graph.persistence")


class KnowledgeGraphPersistence:
    """
    Persists knowledge graph to database.
    
    Features:
    - Full snapshot backup
    - Incremental updates
    - Version history
    - Point-in-time recovery
    """
    
    def __init__(self, db: Session):
        self.db = db
        logger.info("KnowledgeGraphPersistence initialized")
    
    async def save_graph(
        self, 
        graph: TravelKnowledgeGraph, 
        description: str = ""
    ) -> str:
        """
        Save complete graph snapshot to database.
        
        Args:
            graph: TravelKnowledgeGraph instance
            description: Optional description
            
        Returns:
            snapshot_id
        """
        try:
            import uuid
            snapshot_id = str(uuid.uuid4())
            
            # Serialize all data
            nodes_data = self._serialize_nodes(graph)
            edges_data = self._serialize_edges(graph)
            station_patterns = self._serialize_station_patterns(graph)
            route_patterns = self._serialize_route_patterns(graph)
            user_preferences = self._serialize_user_preferences(graph)
            
            # Create snapshot record
            snapshot = KnowledgeGraphSnapshot(
                snapshot_name=f"Graph Snapshot {snapshot_id[:8]}",
                version="1.0.0",
                total_stations=len(graph.graph.nodes),
                total_routes=len(graph.graph.edges),
                total_users=len(graph.user_preferences),
                total_interactions=graph.total_interactions,
                graph_data=json.loads(nodes_data),
                preferences_data=json.loads(user_preferences) if user_preferences else {},
                patterns_data=json.loads(route_patterns) if route_patterns else {},
                description=description
            )
            
            self.db.add(snapshot)
            
            # Also save individual nodes and edges for incremental updates
            await self._save_nodes(graph)
            await self._save_edges(graph)
            
            self.db.commit()
            
            logger.info(f"Graph saved: snapshot_id={snapshot_id}, nodes={len(graph.graph.nodes)}")
            
            return snapshot_id
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to save graph: {e}")
            raise
    
    async def load_graph(
        self, 
        snapshot_id: str = None,
        as_of: datetime = None
    ) -> Optional[TravelKnowledgeGraph]:
        """
        Load graph from database.
        
        Args:
            snapshot_id: Specific snapshot to load (default: latest)
            as_of: Point-in-time recovery (not yet implemented)
            
        Returns:
            TravelKnowledgeGraph instance or None
        """
        try:
            if snapshot_id:
                snapshot = self.db.query(KnowledgeGraphSnapshot).filter(
                    KnowledgeGraphSnapshot.snapshot_name.like(f"%{snapshot_id[:8]}%")
                ).first()
            else:
                snapshot = self.db.query(KnowledgeGraphSnapshot).order_by(
                    KnowledgeGraphSnapshot.created_at.desc()
                ).first()
            
            if not snapshot:
                logger.warning("No graph snapshot found")
                return None
            
            # Create new graph instance
            graph = TravelKnowledgeGraph()
            
            # Deserialize data
            self._deserialize_graph(graph, snapshot)
            
            logger.info(f"Graph loaded: snapshot_name={snapshot.snapshot_name}")
            
            return graph
            
        except Exception as e:
            logger.error(f"Failed to load graph: {e}")
            raise
    
    async def save_incremental(
        self, 
        graph: TravelKnowledgeGraph,
        node_updates: List[Dict] = None,
        edge_updates: List[Dict] = None
    ) -> str:
        """
        Save incremental updates to graph.
        
        Args:
            graph: TravelKnowledgeGraph instance
            node_updates: List of node updates
            edge_updates: List of edge updates
            
        Returns:
            snapshot_id
        """
        try:
            # Save individual updates
            if node_updates:
                await self._save_node_updates(node_updates)
            
            if edge_updates:
                await self._save_edge_updates(edge_updates)
            
            # Create new snapshot
            snapshot_id = await self.save_graph(graph, description="Incremental update")
            
            return snapshot_id
            
        except Exception as e:
            logger.error(f"Failed to save incremental update: {e}")
            raise
    
    def get_snapshot_history(
        self, 
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """Get history of graph snapshots"""
        snapshots = self.db.query(KnowledgeGraphSnapshot).order_by(
            KnowledgeGraphSnapshot.created_at.desc()
        ).limit(limit).all()
        
        return [
            {
                "snapshot_id": s.snapshot_name,
                "created_at": s.created_at.isoformat(),
                "node_count": s.total_stations,
                "edge_count": s.total_routes,
                "description": s.description
            }
            for s in snapshots
        ]
    
    async def delete_snapshot(self, snapshot_id: str) -> bool:
        """Delete a specific snapshot"""
        try:
            result = self.db.query(KnowledgeGraphSnapshot).filter(
                KnowledgeGraphSnapshot.snapshot_name.like(f"%{snapshot_id[:8]}%")
            ).delete()
            
            self.db.commit()
            
            return result > 0
            
        except Exception as e:
            self.db.rollback()
            logger.error(f"Failed to delete snapshot: {e}")
            return False
    
    # Serialization methods
    
    def _serialize_nodes(self, graph: TravelKnowledgeGraph) -> str:
        """Serialize graph nodes to JSON"""
        nodes = []
        for node_id in graph.graph.nodes:
            node_data = graph.graph.nodes[node_id]
            nodes.append({
                "id": node_id,
                "type": node_data.get("type", "unknown"),
                "attributes": dict(node_data)
            })
        return json.dumps(nodes)
    
    def _serialize_edges(self, graph: TravelKnowledgeGraph) -> str:
        """Serialize graph edges to JSON"""
        edges = []
        for source, target, edge_data in graph.graph.edges(data=True):
            edges.append({
                "source": source,
                "target": target,
                "type": edge_data.get("type", "unknown"),
                "attributes": dict(edge_data)
            })
        return json.dumps(edges)
    
    def _serialize_station_patterns(self, graph: TravelKnowledgeGraph) -> str:
        """Serialize station patterns to JSON"""
        patterns = {}
        for code, pattern in graph.station_patterns.items():
            patterns[code] = {
                "code": pattern.code,
                "name": pattern.name,
                "region": pattern.region,
                "zone": pattern.zone,
                "connectivity_score": pattern.connectivity_score,
                "peak_hours": pattern.peak_hours,
                "avg_delay": getattr(pattern, 'avg_delay', getattr(pattern, 'avg_delay_minutes', 0.0)),
                "total_trains": getattr(pattern, 'total_trains', 0)
            }
        return json.dumps(patterns)
    
    def _serialize_route_patterns(self, graph: TravelKnowledgeGraph) -> str:
        """Serialize route patterns to JSON"""
        patterns = {}
        for key, pattern in graph.route_patterns.items():
            if isinstance(pattern, dict):
                patterns[key] = pattern
            else:
                patterns[key] = {
                    "source": getattr(pattern, 'source', ''),
                    "destination": getattr(pattern, 'destination', ''),
                    "avg_duration": getattr(pattern, 'avg_duration', 0),
                    "frequency": getattr(pattern, 'frequency', 0),
                    "reliability": getattr(pattern, 'reliability', 0.9),
                    "searches": getattr(pattern, 'searches', 0),
                    "bookings": getattr(pattern, 'bookings', 0)
                }
        return json.dumps(patterns)
    
    def _serialize_user_preferences(self, graph: TravelKnowledgeGraph) -> str:
        """Serialize user preferences to JSON"""
        prefs = {}
        for user_id, pref in graph.user_preferences.items():
            if isinstance(pref, dict):
                prefs[user_id] = pref
            else:
                prefs[user_id] = {
                    "user_id": getattr(pref, 'user_id', user_id),
                    "preferred_class": getattr(pref, 'preferred_class', 'SL'),
                    "preferred_time_morning": getattr(pref, 'preferred_time_morning', False),
                    "flexibility_score": getattr(pref, 'flexibility_score', 0.5),
                    "price_sensitivity": getattr(pref, 'price_sensitivity', 0.5)
                }
        return json.dumps(prefs)
    
    def _deserialize_graph(
        self, 
        graph: TravelKnowledgeGraph, 
        snapshot: KnowledgeGraphSnapshot
    ) -> None:
        """Deserialize snapshot into graph instance"""
        import networkx as nx
        
        # Deserialize nodes
        nodes = json.loads(snapshot.graph_data or "[]")
        for node in nodes:
            graph.graph.add_node(
                node["id"],
                type=node["type"],
                **node.get("attributes", {})
            )
        
        # Deserialize edges from incremental edge storage, if present
        saved_edges = self.db.query(KnowledgeGraphEdgeModel).all()
        for edge in saved_edges:
            graph.graph.add_edge(
                edge.source_id,
                edge.target_id,
                type=edge.edge_type,
                **(edge.attributes or {})
            )
        
        # Deserialize station patterns if present in patterns_data
        patterns_data = json.loads(snapshot.patterns_data or "{}")
        station_patterns = patterns_data.get("stations", {}) if isinstance(patterns_data, dict) else {}
        for code, data in station_patterns.items():
            graph.station_patterns[code] = StationNode(
                code=data.get("code", code),
                name=data.get("name", ""),
                region=data.get("region", ""),
                zone=data.get("zone", ""),
                connectivity_score=data.get("connectivity_score", 0.5)
            )
        
        # Deserialize route patterns
        route_patterns = patterns_data.get("routes", patterns_data) if isinstance(patterns_data, dict) else {}
        for key, data in route_patterns.items():
            if isinstance(data, dict) and "source" in data:
                graph.route_patterns[key] = RoutePattern(
                    source=data["source"],
                    destination=data["destination"]
                )
        
        # Deserialize user preferences
        user_prefs = json.loads(snapshot.preferences_data or "{}")
        for user_id, data in user_prefs.items():
            from services.knowledge_graph_service import UserPreference
            graph.user_preferences[user_id] = UserPreference(
                user_id=data["user_id"],
                preferred_class=data.get("preferred_class", "SL"),
                preferred_time_morning=data.get("preferred_time_morning", False),
                flexibility_score=data.get("flexibility_score", 0.5),
                price_sensitivity=data.get("price_sensitivity", 0.5)
            )
    
    async def _save_nodes(self, graph: TravelKnowledgeGraph) -> None:
        """Save individual nodes to database"""
        for node_id in graph.graph.nodes:
            node_data = graph.graph.nodes[node_id]
            
            existing = self.db.query(KnowledgeGraphNodeModel).filter(
                KnowledgeGraphNodeModel.node_id == node_id
            ).first()
            
            if existing:
                existing.attributes = dict(node_data)
                existing.updated_at = datetime.utcnow()
            else:
                node = KnowledgeGraphNodeModel(
                    node_id=node_id,
                    node_type=node_data.get("type", "unknown"),
                    attributes=dict(node_data)
                )
                self.db.add(node)
    
    async def _save_edges(self, graph: TravelKnowledgeGraph) -> None:
        """Save individual edges to database"""
        for source, target, edge_data in graph.graph.edges(data=True):
            existing = self.db.query(KnowledgeGraphEdgeModel).filter(
                and_(
                    KnowledgeGraphEdgeModel.source_id == source,
                    KnowledgeGraphEdgeModel.target_id == target
                )
            ).first()
            
            if existing:
                existing.weight = edge_data.get("weight", 1.0)
                existing.attributes = dict(edge_data)
                existing.updated_at = datetime.utcnow()
            else:
                edge = KnowledgeGraphEdgeModel(
                    source_id=source,
                    target_id=target,
                    edge_type=edge_data.get("type", "unknown"),
                    weight=edge_data.get("weight", 1.0),
                    attributes=dict(edge_data)
                )
                self.db.add(edge)
    
    async def _save_node_updates(self, updates: List[Dict]) -> None:
        """Save node updates"""
        for update in updates:
            node = self.db.query(KnowledgeGraphNodeModel).filter(
                KnowledgeGraphNodeModel.node_id == update["node_id"]
            ).first()
            
            if node:
                node.attributes.update(update.get("attributes", {}))
                node.updated_at = datetime.utcnow()
    
    async def _save_edge_updates(self, updates: List[Dict]) -> None:
        """Save edge updates"""
        for update in updates:
            edge = self.db.query(KnowledgeGraphEdgeModel).filter(
                and_(
                    KnowledgeGraphEdgeModel.source_id == update["source_id"],
                    KnowledgeGraphEdgeModel.target_id == update["target_id"]
                )
            ).first()
            
            if edge:
                if "weight" in update:
                    edge.weight = update["weight"]
                if "attributes" in update:
                    edge.attributes.update(update["attributes"])
                edge.updated_at = datetime.utcnow()


# Global instance factory
_persistence_instance = None

def get_knowledge_graph_persistence(db: Optional[Session] = None) -> KnowledgeGraphPersistence:
    """Get or create persistence instance"""
    global _persistence_instance
    if _persistence_instance is None:
        from database.session import SessionLocal
        db_session = db or SessionLocal()
        _persistence_instance = KnowledgeGraphPersistence(db_session)
    return _persistence_instance


# Export for external use
__all__ = [
    'KnowledgeGraphPersistence',
    'KnowledgeGraphSnapshot',
    'KnowledgeGraphNodeModel',
    'KnowledgeGraphEdgeModel',
    'get_knowledge_graph_persistence'
]
