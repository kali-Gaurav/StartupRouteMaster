from backend.database import SessionLocal
from backend.services.route_engine import route_engine

print('before_loaded=', route_engine.is_loaded())

db = SessionLocal()
route_engine.load_graph_from_db(db)
print('after_loaded=', route_engine.is_loaded())
print('stations_map=', len(route_engine.stations_map))
print('segments_map=', len(route_engine.segments_map))
db.close()
