"""Thin re-export layer for algorithmic/engine primitives.

This places the actual algorithm implementations (graph builder, graph model,
RAPTOR algorithms) under a single `core.engines` namespace while keeping
backward-compatibility with the older `core.route_engine.*` modules.
"""
from ..route_engine.builder import GraphBuilder, ParallelGraphBuilder
from ..route_engine.graph import TimeDependentGraph, StaticGraphSnapshot, RealtimeOverlay
from ..route_engine.raptor import OptimizedRAPTOR, HybridRAPTOR

__all__ = [
    "GraphBuilder",
    "ParallelGraphBuilder",
    "TimeDependentGraph",
    "StaticGraphSnapshot",
    "RealtimeOverlay",
    "OptimizedRAPTOR",
    "HybridRAPTOR",
]
