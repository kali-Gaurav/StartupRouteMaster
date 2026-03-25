from services.rapidapi_provider import rapidapi_provider
import asyncio

async def main():
    await rapidapi_provider.initialize()
    result = await rapidapi_provider._make_request('GET', '/api/v1/getFare', {'trainNo': '19038', 'fromStationCode': 'bvi', 'toStationCode': 'st'})
    print(result)
    await rapidapi_provider.shutdown()

if __name__ == "__main__":
    asyncio.run(main())
