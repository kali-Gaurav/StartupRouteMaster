from backend.services.route_engine import route_engine as re
from datetime import date

# Setup stations
re.stations_map = {
    "S1": {"name": "A", "safety_score": 80},
    "S2": {"name": "B", "safety_score": 10},
    "S3": {"name": "C", "safety_score": 80},
    "S4": {"name": "D", "safety_score": 90}
}
re.station_name_to_id = {"a": "S1", "b": "S2", "c": "S3", "d": "S4"}

# Two routes: via B and via D
s1 = {"id": "seg_ab", "source_station_id": "S1", "dest_station_id": "S2", "departure": "08:00", "arrival": "09:40", "duration": 100, "cost": 70.0, "operating_days": "1111111", "vehicle_id": "v1", "mode": "train"}
s2 = {"id": "seg_bc", "source_station_id": "S2", "dest_station_id": "S3", "departure": "09:50", "arrival": "10:40", "duration": 50, "cost": 50.0, "operating_days": "1111111", "vehicle_id": "v2", "mode": "train"}

s3 = {"id": "seg_ad", "source_station_id": "S1", "dest_station_id": "S4", "departure": "08:00", "arrival": "09:30", "duration": 90, "cost": 40.0, "operating_days": "1111111", "vehicle_id": "v3", "mode": "train"}
s4 = {"id": "seg_dc", "source_station_id": "S4", "dest_station_id": "S3", "departure": "09:45", "arrival": "11:00", "duration": 75, "cost": 60.0, "operating_days": "1111111", "vehicle_id": "v4", "mode": "train"}

re.segments_map = {s['id']: s for s in [s1, s2, s3, s4]}
re.route_segments = {"route_1": [s1, s2], "route_2": [s3, s4]}
re._is_loaded = True

# Rebuild indices and run RAPTOR
re._build_route_indices()
print('routes_by_station:', re.routes_by_station)
paths = re._raptor_mvp('S1', 'S3', date(2026,2,16), max_rounds=3)
print('\nRAPTOR returned {} path(s)'.format(len(paths)))
for p in paths:
    print(' Path segments:', [seg['id'] for seg in p], ' total_time=', sum(seg['duration'] for seg in p), ' cost=', sum(seg['cost'] for seg in p))

# Also show constructed routes
import asyncio

async def main():
    routes = [await re._construct_route_from_segment_list('A','C', p, None) for p in paths]
    for r in routes:
        print('\nConstructed route id:', r['id'], 'feasibility=', r.get('feasibility_score'))

asyncio.run(main())
