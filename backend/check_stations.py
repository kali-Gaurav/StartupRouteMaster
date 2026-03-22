import asyncio
from database.session import SessionTransit, initialize_database_pools
from database.models import Stop

async def test():
    await initialize_database_pools()
    db = SessionTransit()
    for code in ['PGT', 'KOTA', 'GHY', 'BNC', 'NDLS', 'CSMT']:
        s = db.query(Stop).filter(Stop.code == code).first()
        print(f"{code}: ID={s.id if s else 'NOT FOUND'}, Code={s.code if s else 'N/A'}")
    
    db.close()

if __name__ == "__main__":
    asyncio.run(test())
