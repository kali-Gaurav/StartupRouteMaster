from services.rapidapi_provider import rapidapi_provider
import asyncio

async def main():
    await rapidapi_provider.initialize()
    result = await rapidapi_provider.get_trains_between_stations('NDLS', 'BCT')
    print(result)
    await rapidapi_provider.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
