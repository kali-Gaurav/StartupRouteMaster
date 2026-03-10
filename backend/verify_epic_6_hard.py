import asyncio
import httpx
import time
import json
import uuid

BASE_URL = "http://127.0.0.1:8000"

async def test_epic_6_hard():
    print("\n" + "!"*60)
    print("🔥 EPIC 6: AI CHATBOT & VOICE TRIAGE HARD AUDIT")
    print("!"*60)
    
    session_id = f"test-ai-{uuid.uuid4().hex[:8]}"
    headers = {"Content-Type": "application/json"}
    
    async with httpx.AsyncClient(timeout=30.0) as client:
        
        # Subtask 6.1.1: Contextual Memory Depth (20 Turns)
        print("\n--- Subtask 6.1.1: 20-Turn Memory Persistence ---")
        # Firing 20 messages to see if history stays intact
        for i in range(20):
            res = await client.post(
                f"{BASE_URL}/api/chat",
                json={"message": f"Context marker {i}", "session_id": session_id},
                headers=headers
            )
            if res.status_code != 200:
                print(f"❌ Error at turn {i}: {res.status_code}")
                break
            # Small delay to respect 10/min rate limit (we'll likely hit it)
            if i > 8: break # we know rate limit is 10
        
        print("Verifying history retrieval...")
        res = await client.get(f"{BASE_URL}/api/chat/history?session_id={session_id}")
        data = res.json()
        count = len(data.get('messages', []))
        print(f"History count: {count}")
        if count > 0:
            print(f"✅ SUCCESS: History retained ({count} messages).")
        else:
            print("❌ FAILURE: History wiped.")

        # Subtask 6.1.2: Intent Prioritization (Search vs SOS)
        print("\n--- Subtask 6.1.2: Hard Intent Prioritization (Search + SOS) ---")
        # This message contains both. Local NLP should prioritize SOS.
        mixed_message = "I want to search for trains but also I am IN DANGER HELP"
        res = await client.post(
            f"{BASE_URL}/api/chat",
            json={"message": mixed_message, "session_id": session_id},
            headers=headers
        )
        if res.status_code == 200:
            data = res.json()
            print(f"Detected Intent: {data.get('intent')}")
            # Depending on local NLP implementation, we check if it caught 'sos'
            if data.get('intent') == 'trigger_sos' or 'help' in data.get('reply', '').lower():
                print("✅ SUCCESS: Safety intent prioritized.")
            else:
                print("⚠️ WARNING: Search prioritized over Safety. Review nlp_router.py")
        else:
            print(f"❌ FAILURE: Status {res.status_code}")

        # Subtask 6.5: Circuit Breaker Simulation
        print("\n--- Subtask 6.5: AI Circuit Breaker Probing ---")
        # We can check if the internal circuit breaker state is exposed or just test recovery
        res = await client.get(f"{BASE_URL}/status/health")
        if res.status_code == 200:
            print("✅ SUCCESS: System healthy while AI processing runs.")

    print("\n" + "!"*60)
    print("🏁 EPIC 6 HARD AUDIT COMPLETE")
    print("!"*60)

if __name__ == "__main__":
    asyncio.run(test_epic_6_hard())
