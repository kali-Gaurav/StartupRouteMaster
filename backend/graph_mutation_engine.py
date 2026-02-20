"""Compatibility shim for `backend.graph_mutation_engine`.

Many modules still import `backend.graph_mutation_engine` after consolidation —
this module re-exports the canonical implementation that now lives under
`backend.platform.graph.train_state` so older import sites keep working.
"""
from backend.platform.graph.train_state import (
    GraphMutationEngine,
    initialize_graph_mutation,
    graph_mutation_engine,
    TrainState,
    TrainStateStore,
)

__all__ = [
    "GraphMutationEngine",
    "initialize_graph_mutation",
    "graph_mutation_engine",
    "TrainState",
    "TrainStateStore",
]
