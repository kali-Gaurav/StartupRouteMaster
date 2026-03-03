import sys
import os
from datetime import datetime

# Add the backend directory to the sys.path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from supabase_client import supabase
from database.config import Config

def test_connection():
    print(f"Testing Supabase connection to: {Config.SUPABASE_URL}")
    try:
        # Simple query to check if we can reach the DB via Supabase
        res = supabase.table('users').select('count', count='exact').limit(1).execute()
        print("✅ Supabase connection successful!")
        print(f"Data response: {res}")
    except Exception as e:
        print(f"❌ Supabase connection failed: {e}")

def test_auth_client():
    print("\nTesting Supabase Auth client...")
    try:
        # This will fail if the key is invalid or URL is wrong
        print(f"Auth client initialized: {supabase.auth is not None}")
        
        # Test if we can at least call an auth method
        try:
            supabase.auth.get_user("invalid_token")
            print("Auth get_user called (expected failure/error but no crash)")
        except Exception as auth_e:
            print(f"Auth get_user produced expected exception: {auth_e}")
            
    except Exception as e:
        print(f"❌ Supabase Auth client test failed: {e}")

if __name__ == "__main__":
    test_connection()
    test_auth_client()
