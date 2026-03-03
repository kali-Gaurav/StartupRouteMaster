"""Utility for manually exercising route engines (Turbo, FastPath, HybridRAPTOR).

Run from backend workspace (activate venv) to compare outputs/time for a given source, dest and date.

Usage:
    python -m scripts.engine_diagnostics KOAA NDLS 2026-03-04
"""
import sys
import time
from datetime import datetime

# import the engines
from services.search_service import SearchService
from core.route_engine.turbo_router import TurboRouter
from core.route_engine.fast_router import FastPathRouter
from core.route_engine import RouteEngine


def main(argv):
    if len(argv) < 4:
        print("Usage: python -m scripts.engine_diagnostics SOURCE DEST YYYY-MM-DD")
        sys.exit(1)

    source, dest, date_str = argv[1], argv[2], argv[3]
    try:
        date = datetime.strptime(date_str, "%Y-%m-%d")
    except Exception:
        print("Date must be in YYYY-MM-DD format")
        sys.exit(1)

    print(f"Testing engines for {source} -> {dest} on {date.date()}")

    # turbo
    turbo = TurboRouter()
    start = time.time()
    t_results = turbo.find_routes(source, dest, date, limit=20)
    elapsed = (time.time() - start) * 1000.0
    print(f"TurboRouter: {len(t_results)} routes in {elapsed:.1f}ms")

    # fast router requires route engine to build graph
    engine = RouteEngine()
    # call initialize synchronously for now
    import asyncio
    asyncio.get_event_loop().run_until_complete(engine.initialize(date_override=date))
    graph = asyncio.get_event_loop().run_until_complete(engine._get_current_graph(date))
    fast = FastPathRouter(graph)
    start = time.time()
    # we arbitrarily use RouteConstraints() default
    from core.route_engine.constraints import RouteConstraints
    f_results = fast.find_routes(source, dest, date, RouteConstraints())
    elapsed = (time.time() - start) * 1000.0
    print(f"FastPathRouter: {len(f_results)} routes in {elapsed:.1f}ms")

    # hybrid raptor via engine.search_routes
    start = time.time()
    r_results = asyncio.get_event_loop().run_until_complete(
        engine.search_routes(source, dest, date)
    )
    elapsed = (time.time() - start) * 1000.0
    print(f"HybridRAPTOR (via RouteEngine.search_routes): {len(r_results)} routes in {elapsed:.1f}ms")

    # Summary
    print("\nResults details:\n")
    print("Turbo sample:", t_results[:2])
    print("Fast sample:", [r.to_dict() if hasattr(r, 'to_dict') else str(r) for r in f_results[:2]])
    print("Hybrid sample:", [r.__dict__ for r in r_results[:2]])


if __name__ == '__main__':
    main(sys.argv)
