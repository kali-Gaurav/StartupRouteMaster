"""
🧠 TRAVEL KNOWLEDGE GRAPH — Patent-Level Inefficiency Index
Stores and queries non-obvious travel patterns, station bottlenecks, 
and multi-modal 'cheat codes' to optimize redistribution.
"""

import logging
from typing import List, Dict, Any, Optional, Set
from dataclasses import dataclass, field
from datetime import datetime, time

logger = logging.getLogger(__name__)

@dataclass(slots=True)
class KnowledgeNode:
    """A node in the travel knowledge graph (Station, Train, or Corridor)."""
    id: str
    type: str  # STATION, TRAIN, CORRIDOR
    attributes: Dict[str, Any] = field(default_factory=dict)
    inefficiencies: List[str] = field(default_factory=list)
    tags: Set[str] = field(default_factory=set)

@dataclass(slots=True)
class TravelInsight:
    """An actionable insight from the knowledge graph."""
    title: str
    description: str
    severity: float  # 0-1
    recommendation: str
    impacted_entities: List[str]

class TravelKnowledgeGraph:
    """
    Maintains a semantic layer over the physical transit network.
    Identifies 'Loopholes' and 'Inefficiencies' used by the Redistribution Engine.
    """

    def __init__(self):
        self.nodes: Dict[str, KnowledgeNode] = {}
        self._initialize_static_knowledge()

    def _initialize_static_knowledge(self):
        """Seed the graph with known Indian Railway inefficiencies."""
        # Station Bottlenecks
        self.add_node(KnowledgeNode(
            id="NDLS", type="STATION",
            inefficiencies=["Heavy congestion on Platform 1-5 during evening rush", "Long security queues at Paharganj side"],
            tags={"MAJOR_HUB", "HIGH_TURNOVER"}
        ))
        
        self.add_node(KnowledgeNode(
            id="HWH", type="STATION",
            inefficiencies=["Limited cab access during rain", "Congested foot-over-bridges"],
            tags={"TERMINUS", "CROWDED"}
        ))

        # Corridor Loopholes
        self.add_node(KnowledgeNode(
            id="NDLS-HWH", type="CORRIDOR",
            inefficiencies=["Over-dependence on Rajdhani trains", "Under-utilization of Duronto on certain days"],
            tags={"HIGH_DEMAND", "TRUNK_ROUTE"}
        ))

    def add_node(self, node: KnowledgeNode):
        self.nodes[node.id] = node

    def get_node(self, node_id: str) -> Optional[KnowledgeNode]:
        return self.nodes.get(node_id)

    def query_inefficiencies(self, entity_ids: List[str]) -> List[str]:
        """Returns a list of known issues for the given entities."""
        results = []
        for eid in entity_ids:
            node = self.get_node(eid)
            if node:
                results.extend(node.inefficiencies)
        return list(set(results))

    def get_redistribution_advice(self, source: str, destination: str) -> List[TravelInsight]:
        """
        Provides specific advice for redistributing passengers on a corridor.
        """
        insights = []
        
        # Logic to generate insights based on graph state
        if source == "NDLS" and destination == "HWH":
            insights.append(TravelInsight(
                title="Shatabdi-to-Duronto Bridge",
                description="Rajdhani is at 105% capacity. Duronto (12274) has 20% vacancy and arrives only 3 hours later.",
                severity=0.8,
                recommendation="Suggest Duronto with free lounge access at NDLS to bridge the 3-hour gap.",
                impacted_entities=["12301", "12274"]
            ))
            
        return insights

# Singleton
knowledge_graph = TravelKnowledgeGraph()
