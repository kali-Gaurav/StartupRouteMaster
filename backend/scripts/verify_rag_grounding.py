import sys
import os
import asyncio
from sqlalchemy.orm import Session

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from api.chat import GatewayValidator, RailwayDatabaseTool
from database import get_db, SessionLocal

async def test_rag_grounding():
    db = SessionLocal()
    validator = GatewayValidator(user=None, db=db)
    
    print("--- RAG Database Grounding Verification ---")
    
    # 1. Test Train Schedule Tool Call
    print("\n[Test 1] Querying Schedule for Train 12628...")
    tool_call = {
        "function": {
            "name": "RailwayDatabaseTool",
            "arguments": '{"query_type": "train_schedule", "train_number": "12628"}'
        }
    }
    
    response = await validator.validate_and_execute(tool_call)
    print(f"Response: {response.reply}")
    
    # 2. Test Station Info Tool Call
    print("\n[Test 2] Querying Info for Station NDLS...")
    tool_call = {
        "function": {
            "name": "RailwayDatabaseTool",
            "arguments": '{"query_type": "station_info", "station_code": "NDLS"}'
        }
    }
    
    response = await validator.validate_and_execute(tool_call)
    print(f"Response: {response.reply}")
    
    db.close()

if __name__ == "__main__":
    asyncio.run(test_rag_grounding())
