import sys
import os
sys.path.append('backend')
from app import app

for route in app.routes:
    path = getattr(route, 'path', 'N/A')
    methods = getattr(route, 'methods', 'WS')
    print(f"{methods} {path}")
