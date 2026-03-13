import asyncio
import uuid
import json
import httpx
from datetime import datetime

BASE_URL = "http://localhost:8000/api/chat"

def log_test(name, success, detail=""):
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"[{status}] {name}: {detail}")

async def test_amorphous_input():
    """TC1: 'train' -> clarify"""
    session_id = str(uuid.uuid4())
    async with httpx.AsyncClient() as client:
        res = await client.post(BASE_URL, json={"message": "train", "session_id": session_id})
        data = res.json()
        success = data.get("intent") == "clarify" and len(data.get("actions", [])) >= 2
        log_test("TC1: Amorphous Input", success, f"Intent: {data.get('intent')}")

async def test_cross_turn_memory():
    """TC3: Turn A: 'Delhi to Mumbai' -> Turn B: 'Tomorrow'"""
    session_id = str(uuid.uuid4())
    async with httpx.AsyncClient() as client:
        # Turn A
        await client.post(BASE_URL, json={"message": "Delhi to Mumbai", "session_id": session_id})
        # Turn B
        res = await client.post(BASE_URL, json={"message": "Tomorrow", "session_id": session_id})
        data = res.json()
        # Should have merged Delhi/Mumbai into current search
        success = data.get("trigger_search") is True and \
                  data.get("collected", {}).get("source") == "DELHI" and \
                  data.get("collected", {}).get("destination") == "MUMBAI"
        log_test("TC3: Cross-Turn Memory", success, f"Collected: {data.get('collected')}")

async def test_intent_hijack_sos():
    """TC4: Search -> SOS Hijack"""
    session_id = str(uuid.uuid4())
    async with httpx.AsyncClient() as client:
        await client.post(BASE_URL, json={"message": "Search trains", "session_id": session_id})
        res = await client.post(BASE_URL, json={"message": "SOS HELP", "session_id": session_id})
        data = res.json()
        success = data.get("intent") == "sos"
        log_test("TC4: SOS Intent Hijack", success, f"Intent: {data.get('intent')}")

async def test_entity_overlap_pnr():
    """TC9: PNR Overlap"""
    session_id = str(uuid.uuid4())
    async with httpx.AsyncClient() as client:
        await client.post(BASE_URL, json={"message": "PNR 1234567890", "session_id": session_id})
        res = await client.post(BASE_URL, json={"message": "0987654321", "session_id": session_id})
        data = res.json()
        success = data.get("intent") == "pnr" and "0987654321" in data.get("reply")
        log_test("TC9: PNR Entity Overlap", success, f"Reply: {data.get('reply')}")

async def run_all():
    print("\n--- Task 2.3 & 2.4: Neural Clarification & Stateful Context Verification ---")
    await test_amorphous_input()
    await test_cross_turn_memory()
    await test_intent_hijack_sos()
    await test_entity_overlap_pnr()
    print("---------------------------------------------------------------------------\n")

if __name__ == "__main__":
    asyncio.run(run_all())
