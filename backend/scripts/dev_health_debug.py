from backend.database import SessionLocal
from backend.services.route_engine import route_engine

print("Running local health debug")

s = SessionLocal()
try:
    res = s.execute("SELECT 1")
    print("DB execute ok:", list(res))
except Exception as e:
    print("DB execute failed:", e)
finally:
    s.close()

try:
    print("route_engine.is_loaded() ->", route_engine.is_loaded())
except Exception as e:
    print("route_engine check failed:", e)
