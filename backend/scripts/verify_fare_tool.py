import sys
import os
import asyncio
import json

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from api.chat import GatewayValidator
from database import SessionLocal

async def test_fare_tool():
    db = SessionLocal()
    validator = GatewayValidator(user=None, db=db)
    
    print("--- Fare Calculation Tool Verification ---")
    
    tool_call = {
        "function": {
            "name": "FareCalculationTool",
            "arguments": json.dumps({
                "source": "New Delhi",
                "destination": "Mumbai Central",
                "travel_class": "2A"
            })
        }
    }
    
    print(f"\n[Test] Querying Fare for 2A from Delhi to Mumbai...")
    response = await validator.validate_and_execute(tool_call)
    
    print(f"Reply: {response.reply}")
    if response.actions:
        print(f"Actions: {[a.label for a in response.actions]}")
    
    if "₹" in response.reply and response.actions:
        print("[PASS] Fare calculated and response formatted correctly.")
    else:
        print("[FAIL] Fare calculation or response error.")
        
    db.close()

if __name__ == "__main__":
    asyncio.run(test_fare_tool())
