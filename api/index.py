import sys
import os

# Add the root directory to the sys.path to allow importing from 'backend'
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.app import app

# Vercel needs the app instance to be named 'app' in this file
# or exported as a handler.
handler = app
