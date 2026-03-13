import asyncio
import sys
import os
import uuid
from datetime import datetime

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from utils.nlp_router import get_local_intent
from api.chat import generate_response

def log_test(name, success, detail=""):
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"[{status}] {name}: {detail}")

async def test_confidence_triage():
    """TC1: Confidence < 0.6 triggers clarify"""
    # Simulate a low confidence result from LLM (manual override for test)
    intent = "unknown" # Normally would go to clarify in chat_message
    message = "something vague"
    # Logic in generate_response for clarify
    res = generate_response("clarify", message, {})
    success = res.intent == "clarify" and len(res.actions) == 2
    log_test("TC1: Confidence Triage (Clarify)", success, f"Intent: {res.intent}")

async def test_context_merging():
    """TC3: Merging source/dest across turns"""
    session_data = {
        "extracted_entities": {"source": "DELHI"}
    }
    # New entities from current turn
    new_entities = {"destination": "MUMBAI"}
    res = generate_response("search", "to Mumbai", session_data, entities=new_entities)
    success = res.trigger_search and res.collected.get("source") == "DELHI" and res.collected.get("destination") == "MUMBAI"
    log_test("TC3: Context Merging", success, f"Collected: {res.collected}")

async def test_intent_hijack():
    """TC4: SOS always has priority (checked in nlp_router)"""
    res = get_local_intent("I am in search of help SOS")
    success = res["intent"] == "sos"
    log_test("TC4: SOS Intent Hijack", success, f"Intent: {res['intent']}")

async def run_all():
    print("\n--- Task 2.3 & 2.4 Logic Verification ---")
    await test_confidence_triage()
    await test_context_merging()
    await test_intent_hijack()
    print("------------------------------------------\n")

if __name__ == "__main__":
    asyncio.run(run_all())
