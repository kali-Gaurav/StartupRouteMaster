import sys
import os

# Ensure workspace root is on sys.path so local packages (routemaster_agent, backend, etc.) can be imported during pytest runs.
# Determine the workspace root based on the location of this file, not the
# current working directory. Previously we used os.getcwd(), which meant that
# running pytest from `backend/` added that folder to sys.path. Since
# `backend/platform` exists, it would then shadow the standard library module
# `platform` and break imports (e.g. Faker during test collection).
ROOT = os.path.abspath(os.path.dirname(__file__))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
