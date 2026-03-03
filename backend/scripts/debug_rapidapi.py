import asyncio
import aiohttp
import os
import sys

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))

async def test_endpoint(name, url, params, headers):
    print(f"\n--- Testing {name} ---")
    print(f"URL: {url}")
    print(f"Params: {params}")
    try:
        timeout = aiohttp.ClientTimeout(total=30)
        async with aiohttp.ClientSession(timeout=timeout) as session:
            async with session.get(url, headers=headers, params=params) as resp:
                print(f"Status: {resp.status}")
                data = await resp.json()
                print(f"Response: {data}")
                return data
    except Exception as e:
        print(f"Error in {name}: {e}")
        return None

async def main():
    api_key = os.getenv("RAPIDAPI_KEY") or "e0adaea886msh3fb9b9456cad9ccp17a317jsna7fe7b2fe0b6"
    headers = {
        "x-rapidapi-key": api_key,
        "x-rapidapi-host": "irctc1.p.rapidapi.com"
    }

    # EXACT PARAMETERS FROM USER'S SUCCESSFUL EXAMPLE
    # trainNo * 16378, fromStationCode * PGT, toStationCode * BNC, classType * 2S, date * 04-03-2026
    params_user = {
        "classType": "2S",
        "fromStationCode": "PGT",
        "quota": "GN",
        "toStationCode": "BNC",
        "trainNo": "16378",
        "date": "04-03-2026"
    }
    
    await test_endpoint("v2 User Exact Example (04-03-2026)", 
                        "https://irctc1.p.rapidapi.com/api/v2/checkSeatAvailability", 
                        params_user, headers)

    params_user_yyyy = params_user.copy()
    params_user_yyyy["date"] = "2026-03-04"
    await test_endpoint("v2 User Exact Example (2026-03-04)", 
                        "https://irctc1.p.rapidapi.com/api/v2/checkSeatAvailability", 
                        params_user_yyyy, headers)

if __name__ == "__main__":
    asyncio.run(main())
