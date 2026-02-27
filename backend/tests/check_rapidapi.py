import asyncio, os
from core.route_engine.data_provider import DataProvider

async def main():
    provider = DataProvider()
    print("rapidapi_client object:", provider.rapidapi_client)
    if provider.rapidapi_client:
        print("attempting seat availability call...")
        res = await provider.rapidapi_client.get_seat_availability("12951","NDLS","MMCT","2026-03-15")
        print("seat availability result:", res)
    else:
        print("No client initialized (likely missing RAPIDAPI_KEY)")

if __name__ == '__main__':
    asyncio.run(main())
