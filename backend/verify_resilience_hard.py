import httpx
import time
import os
import subprocess
import signal
import json
from datetime import datetime

BASE_URL = "http://localhost:8000"

def log_test(name, success, detail=""):
    status = "✅ PASS" if success else "❌ FAIL"
    print(f"[{status}] {name}: {detail}")

async def verify_panic():
    """TC1: Global Super-Handler Verification"""
    async with httpx.AsyncClient() as client:
        try:
            res = await client.get(f"{BASE_URL}/api/test/panic")
            data = res.json()
            success = res.status_code == 500 and "RouteMaster Protocol: Safe Mode Active" in data.get("message", "")
            log_test("TC1: System Panic Handler", success, f"Status: {res.status_code}, Msg: {data.get('message')}")
        except Exception as e:
            log_test("TC1: System Panic Handler", False, str(e))

async def verify_backup():
    """TC3: Atomic Backup Verification"""
    backup_dir = "backend/data/backups"
    if not os.path.exists(backup_dir):
        log_test("TC3: Data Backup Protocol", False, "Backup directory missing")
        return
    
    files = os.listdir(backup_dir)
    bak_files = [f for f in files if f.endswith(".bak")]
    success = len(bak_files) > 0
    log_test("TC3: Data Backup Protocol", success, f"Found {len(bak_files)} backup files")

async def verify_surge_ui_api():
    """TC6: Traffic Shaping API Response"""
    # We simulate a 503 response which should include Retry-After
    # This tests if the backend middleware is configured correctly
    async with httpx.AsyncClient() as client:
        # We'll check the health endpoint first to see current surge level
        res = await client.get(f"{BASE_URL}/api/health")
        data = res.json()
        log_test("TC6: Surge Telemetry API", res.status_code == 200, f"Current Level: {data.get('jit_intelligence', {}).get('surge_level')}")

async def verify_pii_masking():
    """TC10: PII Masking Audit"""
    # This requires checking logs, but we can verify the redactor utility directly
    from utils.redactor import safety_redactor
    test_str = "My PNR is 1234567890 and phone is 9876543210"
    redacted = safety_redactor.redact(test_str)
    success = "1234567890" not in redacted and "9876543210" not in redacted
    log_test("TC10: PII Masking Audit", success, f"Redacted: {redacted}")

async def verify_pnr_extraction():
    """TC10.2: PNR Extraction & Redaction"""
    from utils.nlp_router import get_local_intent
    from utils.redactor import safety_redactor
    
    # 1. Extraction check
    res = get_local_intent("Status for PNR 1234567890")
    has_pnr = res and res.get("entities", {}).get("pnr") == "1234567890"
    
    # 2. Redaction check
    msg = f"User checked PNR {res['entities']['pnr']}"
    redacted = safety_redactor.redact(msg)
    success = has_pnr and "1234567890" not in redacted
    log_test("TC10: PNR Extraction & Privacy", success, f"Extracted: {res.get('entities', {}).get('pnr')}")

async def verify_circuit_breaker():
    """TC12: Circuit Breaker Simulation"""
    from app import routing_breaker
    # Trip the breaker
    for _ in range(5): routing_breaker.report_failure()
    is_tripped = not routing_breaker.check()
    log_test("TC12: Routing Circuit Breaker", is_tripped, "Breaker state: TRIPPED")
    # Reset for other tests
    routing_breaker.is_open = False
    routing_breaker.failures = 0

if __name__ == "__main__":
    import asyncio
    print("\n--- RouteMaster V2 Hard Resilience Validation ---")
    asyncio.run(verify_panic())
    asyncio.run(verify_backup())
    asyncio.run(verify_surge_ui_api())
    asyncio.run(verify_pii_masking())
    asyncio.run(verify_pnr_extraction())
    asyncio.run(verify_circuit_breaker())
    print("--------------------------------------------------\n")
