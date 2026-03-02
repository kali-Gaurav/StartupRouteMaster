
import sys, os
# ensure package root is in path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from datetime import datetime

from backend.core.route_engine.turbo_router import TurboRouter

router = TurboRouter()
for date in [datetime(2026,3,2), datetime(2026,3,3)]:
    routes = router.find_routes('NDLS','BCT', date)
    print(date.date(), 'found', len(routes), 'routes')
    if routes:
        for r in routes[:3]:
            print('  ', r['train_no'], r['departure'], r['arrival'])
