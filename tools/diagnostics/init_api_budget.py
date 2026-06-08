import asyncio
import os
import sys

# Ensure backend is in sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

import backend.database.session as session_mod
from backend.database.models import APIBudget
from sqlalchemy import select

async def init_budget():
    print("Initializing API Budget table...")
    # Trigger database initialization
    from backend.core.container import container
    from backend.database.session import database_service
    await database_service.init()
    
    from backend.database.session import AsyncSessionUser, init_db
    
    # Ensure table exists
    await init_db(["api_budgets"])
    
    async with AsyncSessionUser() as session:
        # Check if RapidAPI budget exists
        query = select(APIBudget).filter(APIBudget.provider_name == "RapidAPI")
        result = await session.execute(query)
        budget = result.scalar_one_or_none()
        
        if not budget:
            print("Creating default RapidAPI budget entry...")
            new_budget = APIBudget(
                provider_name="RapidAPI",
                monthly_limit=100.0,
                current_spend=0.0,
                cost_per_request=0.01
            )
            session.add(new_budget)
            await session.commit()
            print("DONE: RapidAPI budget entry created.")
        else:
            print(f"DONE: RapidAPI budget exists: ${budget.current_spend} / ${budget.monthly_limit}")

if __name__ == "__main__":
    asyncio.run(init_budget())
