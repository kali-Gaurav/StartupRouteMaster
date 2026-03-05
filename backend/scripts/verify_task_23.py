import httpx
import asyncio
import time

async def verify():
    print("--- 🗣️ Task 23: Language-Agnostic Phonetic Keyword Hashing Verification ---")
    
    url_base = "http://localhost:8000/api/sos/"
    
    async with httpx.AsyncClient() as client:
        # 1. Test Phonetic English (Heeelp vs Help)
        print("\n[Test 1] Testing phonetic English: 'Pleeese Heeeelp me'...")
        payload1 = {"lat": 28.6139, "lng": 77.2090, "name": "Phonetic User 1", "extra": "Pleeese Heeeelp me"}
        res1 = await client.post(url_base, json=payload1)
        data1 = res1.json()
        print(f"Category: {data1.get('category')}")

        # 2. Test Phonetic Hindi (Bachaaooo vs Bachao)
        print("\n[Test 2] Testing phonetic Hindi: 'Bachaaoooo mujhey'...")
        payload2 = {"lat": 28.6139, "lng": 77.2090, "name": "Phonetic User 2", "extra": "Bachaaoooo mujhey"}
        res2 = await client.post(url_base, json=payload2)
        data2 = res2.json()
        print(f"Category: {data2.get('category')}")
        
        if data1.get("category") == "security" and data2.get("category") == "security":
            print("\n🏆 TASK 23 VERIFIED: Phonetic signatures successfully matched fuzzy keywords.")
        else:
            print("\n❌ TASK 23 FAILED: Phonetic matching logic failed.")

if __name__ == "__main__":
    time.sleep(5)
    asyncio.run(verify())
