"""
🧠 TRAVEL KNOWLEDGE GRAPH — The "System Memory"
Stores and queries historical travel patterns, station dynamics, and hidden corridor intelligence.
Implements:
  1. Pattern Discovery (Delay corridors, seasonality of popularity)
  2. Amenity Mapping (Station services linked to redistribution incentives)
  3. Reliability Indexing (Historical punctuality per train/day/weather)
  4. Hidden Jump Discovery (Unofficial but efficient transfer bridges)
"""

import logging
import json
import time
from datetime import datetime, date
from typing import List, Dict, Any, Optional, Set, Tuple
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)

# =========================================================================
# SCHEMA
# =========================================================================

class NodeType(Enum):
    STATION = "STATION"
    TRAIN = "TRAIN"
    CORRIDOR = "CORRIDOR"
    SERVICE = "SERVICE"
    EVENT = "EVENT"

class EdgeType(Enum):
    CONNECTS = "CONNECTS"
    DELAYED_BY = "DELAYED_BY"
    POPULAR_IN = "POPULAR_IN"
    OFFERS = "OFFERS"
    TRANSFERS_TO = "TRANSFERS_TO"

@dataclass
class KnowledgeNode:
    id: str
    type: NodeType
    properties: Dict[str, Any] = field(default_factory=dict)
    last_updated: float = field(default_factory=time.time)

@dataclass
class KnowledgeEdge:
    source: str
    target: str
    type: EdgeType
    weight: float = 1.0
    properties: Dict[str, Any] = field(default_factory=dict)

# =========================================================================
# STORE
# =========================================================================

class TravelKnowledgeGraph:
    """
    Graph-based storage for RouteMaster intelligence.
    Uses an in-memory adjacency list for low-latency queries in the MVP.
    """

    def __init__(self):
        self.nodes: Dict[str, KnowledgeNode] = {}
        self.edges: List[KnowledgeEdge] = []
        self._adjacency: Dict[str, List[KnowledgeEdge]] = {}

    def add_node(self, node_id: str, node_type: NodeType, properties: Dict[str, Any] = None):
        self.nodes[node_id] = KnowledgeNode(node_id, node_type, properties or {})
        if node_id not in self._adjacency:
            self._adjacency[node_id] = []

    def add_edge(self, source: str, target: str, edge_type: EdgeType, weight: float = 1.0, properties: Dict[str, Any] = None):
        if source not in self.nodes or target not in self.nodes:
            logger.warning(f"Knowledge Graph: Attempted to link missing nodes {source} -> {target}")
            return
        
        edge = KnowledgeEdge(source, target, edge_type, weight, properties or {})
        self.edges.append(edge)
        self._adjacency[source].append(edge)

    # --- Intelligence Queries ---

    def get_station_reliability(self, station_code: str) -> float:
        """Calculates a 0-1 reliability score for a station's operations."""
        node = self.nodes.get(station_code)
        if not node: return 0.5
        return node.properties.get("reliability", 0.5)

    def find_hidden_jumps(self, from_station: str) -> List[Dict[str, Any]]:
        """Discovers non-GTFS transfer opportunities (e.g., station bridges)."""
        jumps = []
        for edge in self._adjacency.get(from_station, []):
            if edge.type == EdgeType.TRANSFERS_TO:
                jumps.append({
                    "to": edge.target,
                    "mode": edge.properties.get("mode", "WALK"),
                    "time_mins": edge.properties.get("time_mins", 15),
                    "confidence": edge.weight
                })
        return jumps

    def record_incident(self, entity_id: str, incident_type: str, severity: float):
        """Learns from real-time events (delays, cancellations, SOS)."""
        node = self.nodes.get(entity_id)
        if not node: return
        
        # Simple moving average for reliability
        current = node.properties.get("reliability", 0.8)
        new_val = current * 0.9 + (1.0 - severity) * 0.1
        node.properties["reliability"] = round(new_val, 3)
        node.properties["last_incident"] = incident_type
        
        # Hazard Tracking
        if severity > 0.7:
            node.properties["hazard_level"] = severity
            node.properties["hazard_type"] = incident_type
            node.properties["hazardous_until"] = time.time() + 3600 # 1 hour default
            logger.warning(f"⚠️ [KNOWLEDGE] {entity_id} marked as HAZARDOUS (Level: {severity}) due to {incident_type}")
            
        node.last_updated = time.time()

    def get_hazard_level(self, entity_id: str) -> float:
        """Returns the current hazard level (0-1) for an entity."""
        node = self.nodes.get(entity_id)
        if not node: return 0.0
        
        until = node.properties.get("hazardous_until", 0)
        if time.time() > until:
            return 0.0
            
        return node.properties.get("hazard_level", 0.0)

    async def hydrate_from_db(self, db):
        """Initializes knowledge from historical performance data."""
        # Mocking hydration
        logger.info("🧠 [KNOWLEDGE] Hydrating intelligence from DB...")
        
        # Example: Link NDLS to its amenities
        self.add_node("NDLS", NodeType.STATION, {"reliability": 0.85, "name": "New Delhi"})
        self.add_node("LOUNGE_NDLS_1", NodeType.SERVICE, {"name": "Premium Lounge P1", "capacity": 50})
        self.add_edge("NDLS", "LOUNGE_NDLS_1", EdgeType.OFFERS)
        
        # Example: Hidden jump NDLS -> NZM (Delhi Metro Bridge)
        self.add_node("NZM", NodeType.STATION, {"reliability": 0.82, "name": "Hazrat Nizamuddin"})
        self.add_edge("NDLS", "NZM", EdgeType.TRANSFERS_TO, weight=0.95, properties={"mode": "METRO", "time_mins": 25})

# Singleton
knowledge_graph = TravelKnowledgeGraph()
