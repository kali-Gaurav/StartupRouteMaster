import asyncio
import sys
import os
import uuid
from datetime import datetime

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), "backend"))

from utils.nlp_router import get_local_intent
from services.chat_action_dispatcher import chat_dispatcher
from database.session import SessionTransit

def log_test(name, success, detail=""):
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"[{status}] {name}: {detail}")

async def test_pnr_dispatch():
    """TC1: PNR Intent -> PNR Status Service"""
    db = SessionTransit()
    try:
        # Entities extracted by EntityExtractor in real flow
        entities = {"pnr": "1234567890"}
        result = await chat_dispatcher.dispatch("pnr", entities, db, None)
        # Accept either success OR provider confirmed not found (proves link works)
        success = result is not None and ("PNR LOGISTICS ACQUIRED" in result or "PNR Not found" in result)
        log_test("TC1: PNR Intent Dispatch", success, f"Result snippet: {result[:50] if result else 'None'}...")
    finally:
        db.close()

async def test_track_dispatch():
    """TC2: Track Intent -> Live Status Service"""
    db = SessionTransit()
    try:
        entities = {"train_no": "12626"}
        result = await chat_dispatcher.dispatch("track", entities, db, None)
        # result is formatted string
        success = result is not None and "LIVE TELEMETRY" in result
        log_test("TC2: Track Intent Dispatch", success, f"Result snippet: {result[:50] if result else 'None'}...")
    finally:
        db.close()

async def test_bookings_dispatch():
    """TC3: Bookings Intent -> Booking Retrieval"""
    db = SessionTransit()
    try:
        # User is None, should ask to sign in
        result = await chat_dispatcher.dispatch("bookings", {}, db, None)
        success = "Identity Unknown" in result
        log_test("TC3: Bookings Intent Dispatch (Guest)", success, f"Result: {result}")
    finally:
        db.close()

async def run_all():
    print("\n--- Task 2.7: Intent-to-Action Mapping Verification ---")
    
    # Force DB init
    from database.session import initialize_database_pools
    await initialize_database_pools()
    
    await test_pnr_dispatch()
    await test_track_dispatch()
    await test_bookings_dispatch()
    print("------------------------------------------------------\n")

if __name__ == "__main__":
    asyncio.run(run_all())
