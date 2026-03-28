import asyncio
from database.session import SessionTransit, initialize_database_pools
from sqlalchemy import text

async def check():
    await initialize_database_pools()
    s = SessionTransit()
    
    # Check top 5 hubs by segment count
    query = """
        SELECT s.code, s.name, COUNT(*) as c 
        FROM segments seg 
        JOIN stops s ON seg.source_stop_id = s.id 
        GROUP BY s.id 
        ORDER BY c DESC 
        LIMIT 5
    """
    res = s.execute(text(query)).fetchall()
    print("Most Connected Hubs in DB:")
    for r in res:
        print(f"  - {r[0]} ({r[1]}) : {r[2]} segments")

    # Pick the top hub and see where it goes
    if res:
        top_code = res[0][0]
        query2 = f"""
            SELECT s2.code, s2.name 
            FROM segments seg 
            JOIN stops s1 ON seg.source_stop_id = s1.id 
            JOIN stops s2 ON seg.dest_station_id = s2.id 
            WHERE s1.code = '{top_code}' 
            LIMIT 5
        """
        res2 = s.execute(text(query2)).fetchall()
        print(f"Destinations from {top_code}:")
        for r in res2:
            print(f"  -> {r[0]} ({r[1]})")

    s.close()

if __name__ == "__main__":
    asyncio.run(check())
