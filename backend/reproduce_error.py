import sys
import os

# Add current directory to path
sys.path.append(os.getcwd())

try:
    print("Attempting to import api.v3.search...")
    from api.v3 import search
    print("✅ api.v3.search imported successfully.")
except ImportError as e:
    print(f"❌ ImportError: {e}")
    import traceback
    traceback.print_exc()
except Exception as e:
    print(f"❌ Error: {e}")
    import traceback
    traceback.print_exc()
