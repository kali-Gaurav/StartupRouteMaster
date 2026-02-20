import logging
from datetime import datetime
from typing import Optional
from concurrent.futures import ThreadPoolExecutor

from ..route_engine.snapshot_manager import SnapshotManager
from ..route_engine.builder import GraphBuilder
from ..route_engine.graph import TimeDependentGraph, StaticGraphSnapshot, RealtimeOverlay

logger = logging.getLogger(__name__)


class GraphManager:
    """Encapsulates snapshot management and graph-building logic.

    - Central place for snapshot lifecycle (load / build / save)
    - Keeps lightweight in-memory state for the most-recent snapshot
    - Designed to be used by higher-level coordinators (RouteManager / Engine)
    """

    def __init__(self, executor: Optional[ThreadPoolExecutor] = None,
                 snapshot_manager: Optional[SnapshotManager] = None,
                 graph_builder: Optional[GraphBuilder] = None):
        self.executor = executor or ThreadPoolExecutor(max_workers=4)
        self.snapshot_manager = snapshot_manager or SnapshotManager()
        self.graph_builder = graph_builder or GraphBuilder(self.executor, snapshot_manager=self.snapshot_manager)

        # Visible state (kept for compatibility with existing callers)
        self.current_snapshot: Optional[StaticGraphSnapshot] = None
        self.last_snapshot_time: Optional[datetime] = None
        self.current_overlay: RealtimeOverlay = RealtimeOverlay()

    async def ensure_snapshot_for_date(self, date: datetime, rebuild_ttl_seconds: int = 86400) -> StaticGraphSnapshot:
        """Ensure a snapshot for `date` is available (load from disk or build).

        Returns the StaticGraphSnapshot and also updates `self.current_snapshot`.
        """
        needs_rebuild = (
            not self.current_snapshot or
            self.current_snapshot.date.date() != date.date() or
            (self.last_snapshot_time is None) or
            (datetime.utcnow() - self.last_snapshot_time).total_seconds() > rebuild_ttl_seconds
        )

        if needs_rebuild:
            # Try load from disk
            loaded = self.snapshot_manager.load_snapshot(date)
            if loaded:
                self.current_snapshot = loaded
                logger.info(f"GraphManager: loaded snapshot for {date.date()}")
            else:
                # Build via GraphBuilder
                logger.info(f"GraphManager: building snapshot for {date.date()}")
                graph = await self.graph_builder.build_graph(date)
                self.current_snapshot = graph.snapshot

            self.last_snapshot_time = datetime.utcnow()

        return self.current_snapshot

    async def build_graph(self, date: datetime) -> TimeDependentGraph:
        """Convenience wrapper that returns a TimeDependentGraph for `date`.
        This will use existing snapshot if available (copy-on-write overlay still applies).
        """
        await self.ensure_snapshot_for_date(date)
        graph = TimeDependentGraph(self.current_snapshot)
        graph.overlay = self.current_overlay
        return graph
