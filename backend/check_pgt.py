import asyncio
from database.session import SessionTransit, initialize_database_pools
from database.models import Stop

async def test():
    await initialize_database_pools()
    db = SessionTransit()
    s = db.query(Stop).filter(Stop.code == 'PGT').first()
    print(f"PGT: ID={s.id if s else 'NOT FOUND'}, Code={s.code if s else 'N/A'}")
    
    s2 = db.query(Stop).filter(Stop.code == 'KOTA').first()
    print(f"KOTA: ID={s2.id if s2 else 'NOT FOUND'}, Code={s2.code if s2 else 'N/A'}")
    
    db.close()

if __name__ == "__main__":
    asyncio.run(test())
