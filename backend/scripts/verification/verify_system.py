import asyncio
import sys
import subprocess
import os

def run_command(cmd_list):
    print(f"\nRunning: {' '.join(cmd_list)}")
    try:
        # Run using the same python interpreter
        result = subprocess.run([sys.executable] + cmd_list, capture_output=False, text=True)
        return result.returncode == 0
    except Exception as e:
        print(f"❌ Execution failed: {e}")
        return False

async def verify_everything():
    print("====================================================")
    print("  NEXUS SYSTEM INTEGRITY & STABILITY VERIFIER  ")
    print("====================================================\n")
    
    steps = [
        ("ENVIRONMENT", ["diagnostics_cli.py", "env"]),
        ("DATABASE SCHEMA", ["audit_cli.py", "db-audit"]),
        ("DATABASE PREPARE", ["nexus_verify.py", "db-prepare"]),
        ("IDENTITY & LINKING", ["identity_audit.py"]),
        ("GUARDIAN AI", ["diagnostics_cli.py", "diagnose-guardian"]),
        ("MASTER NEXUS AUDIT", ["nexus_verify.py", "master-audit"]),
        ("ENGINE DIAGNOSTIC", ["nexus_verify.py", "engine-diag"]),
        ("SEARCH E2E VERIFY", ["nexus_verify.py", "search-e2e"]),
        ("SECURITY PROBE", ["nexus_verify.py", "security-probe"]),
        ("LOG ROTATION", ["nexus_verify.py", "log-audit"]),
        ("CHAOS RESILIENCE", ["nexus_verify.py", "chaos-test"])
    ]
    
    failed = []
    
    for name, cmd in steps:
        print(f"\n>>> [STEP: {name}]")
        if not run_command(cmd):
            print(f"WARN: {name} encountered issues.")
            failed.append(name)
        else:
            print(f"OK: {name} passed.")

    print("\n" + "="*50)
    if not failed:
        print(" ALL SYSTEMS GREEN. PRODUCTION READY. ")
    else:
        print(f"ERROR: ISSUES FOUND IN: {', '.join(failed)}")
        print("Please check logs above and fix identified gaps.")
    print("="*50)

if __name__ == "__main__":
    asyncio.run(verify_everything())
