
import sys
import os
import asyncio

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

async def verify_app_integrity():
    print("🔍 Verifying app.py integrity...")
    try:
        from backend.app import app
        print("✅ app.py imported successfully.")
        
        # Check if lifespan is correctly defined
        print(f"✅ App Title: {app.title}")
        print(f"✅ App Version: {app.version}")
        
        # Verify middleware registration
        middleware_names = [m.cls.__name__ for m in app.user_middleware]
        print(f"📦 Registered Middlewares: {', '.join(middleware_names)}")
        
        # Essential middlewares must be present
        essentials = ["GlobalLoadShedderMiddleware", "UnifiedJITMiddleware", "AdaptiveGatekeeperMiddleware"]
        for e in essentials:
            if any(e in name for name in middleware_names):
                print(f"✅ Essential middleware '{e}' found.")
            else:
                print(f"❌ Essential middleware '{e}' NOT found!")
                sys.exit(1)
                
        print("🚀 Integrity check PASSED.")
    except Exception as e:
        print(f"❌ Integrity check FAILED: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    asyncio.run(verify_app_integrity())
