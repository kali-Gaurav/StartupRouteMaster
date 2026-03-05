import httpx
import asyncio
import time

async def verify():
    print("--- 🧠 Task 30: Threat Categorization Bayes Classifier Verification ---")
    
    url_base = "http://localhost:8000/api/sos/"
    
    async with httpx.AsyncClient() as client:
        # 1. Test Bayesian Categorization
        print("\n[Step 1] Sending a complex medical sentence...")
        payload = {
            "lat": 28.6139, "lng": 77.2090, 
            "name": "Bayes User",
            "extra": "My chest is heavy and I cannot breathe properly, I might need a doctor."
        }
        res = await client.post(url_base, json=payload)
        data = res.json()
        
        print(f"Detected Category: {data.get('category')}")
        
        if data.get("category") == "medical":
            print("\n🏆 TASK 30 VERIFIED: Bayesian classifier correctly categorized the incident.")
        else:
            print("\n❌ TASK 30 FAILED: Incident categorized as unknown or wrong type.")

if __name__ == "__main__":
    time.sleep(5)
    asyncio.run(verify())
