import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), 'backend'))
from utils.storage import storage

try:
    print("Testing R2 Connection...")
    objects = storage.list_objects()
    print(f"Connection Successful! Object listing test complete (Objects found: {len(objects) if isinstance(objects, list) else 0}).")
except Exception as e:
    print(f"Connection Failed: {e}")
