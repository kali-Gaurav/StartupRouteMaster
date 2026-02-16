import asyncio
from backend.services.route_engine import route_engine as re
from datetime import date

async def main():
    re.stations_map = {'S1': {'name': 'A'}, 'S2': {'name': 'B'}, 'S3': {'name': 'C'}}
    re.station_name_to_id = {'a': 'S1', 'b': 'S2', 'c': 'S3'}

    s1 = {'id': 'seg1', 'source_station_id': 'S1', 'dest_station_id': 'S2', 'departure': '08:00', 'arrival': '09:00', 'duration': 60, 'cost': 50.0, 'operating_days': '1111111', 'vehicle_id': 'v1', 'mode': 'train'}
    s2 = {'id': 'seg2', 'source_station_id': 'S2', 'dest_station_id': 'S3', 'departure': '09:30', 'arrival': '10:30', 'duration': 60, 'cost': 60.0, 'operating_days': '1111111', 'vehicle_id': 'v2', 'mode': 'train'}

    re.segments_map = {'seg1': s1, 'seg2': s2}
    re.route_segments = {'route_v1': [s1], 'route_v2': [s2]}
    re._is_loaded = True

    print('routes_by_station before build:', re.routes_by_station)
    re._build_route_indices()
    print('route_stop_index:', re.route_stop_index)
    print('route_stop_departures:', re.route_stop_departures)
    print('routes_by_station after build:', re.routes_by_station)
    paths = re._raptor_mvp('S1','S3',date(2026,2,16), max_rounds=2)
    from backend.services.cache_service import cache_service
    print('raptor result:', paths)
    if paths:
        constructed = await re._construct_route_from_segment_list('A','C', paths[0], None)
        print('constructed route:', constructed)
    cache_key = f"route:{{}}:{{}}:{{}}:{{}}".format('A','C','2026-02-16', None)
    print('cache available:', cache_service.is_available())
    print('cached value for key', cache_key, '->', cache_service.get(cache_key))
    print('search_routes result:', await re.search_routes('A','C','2026-02-16'))

asyncio.run(main())
