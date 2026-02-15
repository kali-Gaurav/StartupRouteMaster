import sys
import os

# Ensure workspace root is on sys.path so local packages (routemaster_agent, backend, etc.) can be imported during pytest runs.
ROOT = os.path.abspath(os.getcwd())
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
