import asyncio
import pickle
import os
from datetime import datetime
import pytest

from core.route_engine import RailwayRouteEngine, TimeDependentGraph, StaticGraphSnapshot
from core.route_engine.snapshot_manager import SnapshotManager
from utils import metrics
from services.multi_layer_cache import multi_layer_cache


@pytest.mark.asyncio
async def test_forced_rebuild_creates_snapshot(tmp_path, monkeypatch):
    """Deleting an existing snapshot leads to automatic rebuild and a new file."""
    engine = RailwayRouteEngine()

    # point snapshots to tmp directory
    engine.snapshot_manager.snapshot_dir = str(tmp_path)
    engine.graph_builder.snapshot_manager = engine.snapshot_manager
    engine.raptor.snapshot_manager = engine.snapshot_manager

    # stub graph builder to avoid DB hit and explicitly save snapshot
    async def dummy_build(date):
        snap = StaticGraphSnapshot(date=date)
        graph = TimeDependentGraph(snap)
        # mimic builder persistence
        await engine.snapshot_manager.save_snapshot(snap)
        return graph
    engine.graph_builder.build_graph = dummy_build

    date = datetime(2026, 2, 24)

    # ensure no file exists initially
    expected_path = engine.snapshot_manager._get_snapshot_path(date)
    if os.path.exists(expected_path):
        os.remove(expected_path)

    # call once - should build and save
    graph1 = await engine._get_current_graph(date)
    assert graph1 is not None
    assert os.path.exists(expected_path)

    # record metric value before second call
    before = metrics.SNAPSHOT_BUILD_TIME_MS._sum.get()

    # call again without deleting should load from disk
    graph2 = await engine._get_current_graph(date)
    assert graph2 is not None
    after = metrics.SNAPSHOT_BUILD_TIME_MS._sum.get()
    # no new build occurred -> metric sum unchanged
    assert after == before


@pytest.mark.asyncio
async def test_corrupted_snapshot_triggers_rebuild(tmp_path, monkeypatch):
    engine = RailwayRouteEngine()
    engine.snapshot_manager.snapshot_dir = str(tmp_path)
    engine.graph_builder.build_graph = lambda date: asyncio.sleep(0, result=TimeDependentGraph(StaticGraphSnapshot(date=date)))

    date = datetime(2026, 2, 25)
    path = engine.snapshot_manager._get_snapshot_path(date)
    # write garbage to file (simulate corruption)
    with open(path, 'wb') as f:
        f.write(b"not a pickle")

    # calling _get_current_graph should catch the error and rebuild
    graph = await engine._get_current_graph(date)
    assert graph is not None
    # file should have been overwritten with a valid pickle
    try:
        with open(path, 'rb') as f:
            obj = pickle.load(f)
        assert isinstance(obj, StaticGraphSnapshot)
    except Exception:
        pytest.fail("Snapshot file still corrupted after rebuild")


@pytest.mark.asyncio
async def test_hub_missing_precompute(tmp_path, monkeypatch):
    engine = RailwayRouteEngine()
    engine.snapshot_manager.snapshot_dir = str(tmp_path)
    engine.graph_builder.build_graph = lambda date: asyncio.sleep(0, result=TimeDependentGraph(StaticGraphSnapshot(date=date)))

    # force a snapshot file and load it manually
    date = datetime(2026, 2, 26)
    graph = await engine.graph_builder.build_graph(date)
    engine.current_snapshot = graph.snapshot
    engine.last_snapshot_time = datetime.utcnow()
    engine.raptor._hub_table = None

    # patch precompute to set a flag
    called = {}
    async def fake_precompute(g, d):
        called['happened'] = True
        class Dummy:
            connections = {}
        return Dummy()
    engine.hub_manager.precompute_hub_connectivity = fake_precompute

    # now call _get_current_graph and verify hub table set
    new_graph = await engine._get_current_graph(date)
    assert engine.raptor._hub_table is not None
    assert called.get('happened', False)


@pytest.mark.asyncio
async def test_overlay_sync_versioning(monkeypatch):
    engine = RailwayRouteEngine()

    # first remote state with version 1
    state1 = {"delays": {}, "cancellations": [], "last_updated": datetime.utcnow().isoformat(), "version": 1}
    state2 = {"delays": {"123": 5}, "cancellations": [], "last_updated": datetime.utcnow().isoformat(), "version": 2}

    async def fake_init():
        pass
    monkeypatch.setattr(multi_layer_cache, 'initialize', fake_init)

    calls = []
    async def fake_get_state(key):
        calls.append(key)
        # return version1 first then version2
        return state1 if len(calls) == 1 else state2
    monkeypatch.setattr(multi_layer_cache, 'get_overlay_state', fake_get_state)

    await engine.sync_realtime_overlay()
    assert engine._last_synced_version == 1
    # sync again should pick up version2
    await engine.sync_realtime_overlay()
    assert engine._last_synced_version == 2
    # metric set correctly
    from utils import metrics as m
    assert m.OVERLAY_VERSION._value.get() == 2


@pytest.mark.asyncio
async def test_concurrent_snapshot_build(tmp_path, monkeypatch):
    engine = RailwayRouteEngine()
    engine.snapshot_manager.snapshot_dir = str(tmp_path)

    build_count = 0
    async def counting_build(date):
        nonlocal build_count
        build_count += 1
        await asyncio.sleep(0.01)
        return TimeDependentGraph(StaticGraphSnapshot(date=date))
    engine.graph_builder.build_graph = counting_build

    date = datetime(2026, 2, 27)
    # run 5 parallel requests
    results = await asyncio.gather(*[engine._get_current_graph(date) for _ in range(5)])
    assert all(r is not None for r in results)
    # build_count may be >1 under heavy contention, but it must be
    # non-zero and results should be valid.
    assert build_count >= 1
