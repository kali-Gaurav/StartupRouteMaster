# Ensure repository root is on sys.path so tests can import `backend` package when running from `backend/`
import sys
from pathlib import Path
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Any shared pytest fixtures can be added here later (db, client, test data)
