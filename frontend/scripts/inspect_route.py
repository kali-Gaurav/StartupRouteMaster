import sys, os
sys.path.append(os.getcwd())

from backend.database import SessionLocal
from backend.services.search_service import SearchService
from backend.core.route_engine import route_engine
import asyncio
from datetime import datetime

async def inspect():
    db = SessionLocal()
    service = SearchService(db, route_engine_instance=route_engine)
    res = await service.search_routes(source='NDLS', destination='BCT', travel_date='2026-03-25 12:00:00')
    direct = res.get('routes', {}).get('direct', [])
    if not direct:
        print('no direct')
        return
    rt = direct[0]
    print('Route dict:')
    from pprint import pprint
    pprint(rt)
    print('\nNow fetch internal route using NDLS and BCT IDs')
    # get stop ids directly
    from backend.database.models import Stop
    s1 = db.query(Stop).filter(Stop.code == 'NDLS').first()
    s2 = db.query(Stop).filter(Stop.code == 'BCT').first()
    if s1 and s2:
        from backend.core.route_engine.constraints import RouteConstraints
        routes = await route_engine.raptor.find_routes(
            source_stop_id=s1.id,
            dest_stop_id=s2.id,
            departure_date=datetime.fromisoformat('2026-03-25T12:00:00'),
            constraints=RouteConstraints(),
            graph=None
        )
        print('Internal route count', len(routes))
        if routes:
            r = routes[0]
            print('Internal total_cost', r.total_cost)
            print('Number of segments', len(r.segments))
            for seg in r.segments[:10]:
                print(seg)
            if len(r.segments) > 10:
                print('...more segments')

asyncio.run(inspect())
