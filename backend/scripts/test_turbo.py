from core.route_engine.turbo_router import TurboRouter
from datetime import datetime

router = TurboRouter()
print('Tuesday (2026-03-03) search:')
routes = router.find_routes('NDLS','BCT', datetime(2026,3,3))
print(routes)
print('Yesterday (2026-03-02) search:')
routes2 = router.find_routes('NDLS','BCT', datetime(2026,3,2))
print(routes2)
