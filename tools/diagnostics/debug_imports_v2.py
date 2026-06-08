import sys
import os

print(f"Current working directory: {os.getcwd()}")
print("Python Path:")
for p in sys.path:
    print(f"  {p}")

try:
    from core.lifespan import lifespan
    print("Successfully imported core.lifespan")
except ImportError as e:
    print(f"Failed to import core.lifespan: {e}")
