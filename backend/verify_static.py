import sys
import os

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

def verify_logic():
    print("🔍 Static Logic Verification...")
    try:
        from core.middleware.engine import SystemStateManager, SmartMiddleware
        from services.storage_sync import r2_sync_manager
        
        # Check SystemStateManager methods
        sm = SystemStateManager()
        print(f"✅ SystemStateManager initialized. Current state: {sm.get_current_state().name}")
        
        # Check R2SyncManager
        print(f"✅ R2SyncManager initialized. DB paths: {r2_sync_manager.db_paths}")
        
        # Check SmartMiddleware signature
        import inspect
        sig = inspect.signature(SmartMiddleware.__init__)
        print(f"✅ SmartMiddleware __init__ signature: {sig}")
        
        print("✨ Static verification complete.")
    except Exception as e:
        print(f"❌ Static verification failed: {e}")
        import traceback
        traceback.print_exc()

if __name__ == "__main__":
    verify_logic()
