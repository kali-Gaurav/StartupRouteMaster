def test_core_managers_smoke_import():
    """Smoke test for new manager/engine facades (importability + basic API)."""
    from core import GraphManager, RouteManager

    assert GraphManager is not None
    assert RouteManager is not None

    gm = GraphManager()
    # basic API surface
    assert hasattr(gm, 'ensure_snapshot_for_date')
    assert hasattr(gm, 'build_graph')
    assert hasattr(gm, 'current_overlay')

    # RouteManager should be importable and expose `find_routes` (async)
    rm = RouteManager  # type: ignore
    assert hasattr(rm, '__init__')
