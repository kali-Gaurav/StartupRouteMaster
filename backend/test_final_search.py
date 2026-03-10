import asyncio
import httpx

async def test_search_final():
    print("\n" + "="*100)
    print("🚀 FINAL SEARCH DEEP DIVE")
    print("="*100)
    
    async with httpx.AsyncClient(timeout=60.0) as client:
        try:
            res = await client.get(
                "http://127.0.0.1:8000/api/v2/search/unified", 
                params={
                    "source": "NDLS",
                    "destination": "KOTA",
                    "date": "2026-03-15",
                    "quota": "GN"
                }, 
                headers={"X-Dev-Bypass": "TRUE"}
            )
            print(f"   Status: {res.status_code}")
            if res.status_code == 200:
                data = res.json()
                print(f"   Results: {len(data.get('results', []))}")
                print(f"   Session: {data.get('session_id')}")
            else:
                print(f"   Body: {res.text}")
        except Exception as e:
            print(f"   Search Error: {e}")

if __name__ == "__main__":
    asyncio.run(test_search_final())
