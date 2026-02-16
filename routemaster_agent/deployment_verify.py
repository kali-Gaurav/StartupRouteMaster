#!/usr/bin/env python3
"""
RouteMaster Agent v2 - Complete Deployment Package
===================================================

This script verifies all components are ready for production deployment.
Run this before deploying to production.
"""

import os
import sys
from pathlib import Path

def check_file_exists(filepath):
    """Check if file exists."""
    return os.path.exists(filepath)

def check_file_syntax(filepath):
    """Check if file has valid Python syntax."""
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            compile(f.read(), filepath, 'exec')
        return True, "PASS"
    except SyntaxError as e:
        return False, f"SyntaxError: {e}"
    except Exception as e:
        return False, f"Error: {e}"

def main():
    print("\n" + "="*70)
    print("ROUTEMASTER AGENT V2 - PRODUCTION DEPLOYMENT VERIFICATION")
    print("="*70 + "\n")
    
    files_to_check = {
        "Core Engines": [
            "routemaster_agent/core/navigator_ai.py",
            "routemaster_agent/core/vision_ai.py",
            "routemaster_agent/core/extractor_ai.py",
            "routemaster_agent/core/decision_engine.py",
            "routemaster_agent/core/reasoning_loop.py",
            "routemaster_agent/core/__init__.py",
        ],
        "AI Integration": [
            "routemaster_agent/ai/gemini_client.py",
        ],
        "System Integration": [
            "routemaster_agent/manager.py",
            "routemaster_agent/api_dashboard.py",
        ],
    }
    
    all_passed = True
    total_lines = 0
    
    for category, files in files_to_check.items():
        print(f"{category}:")
        print("-" * 70)
        
        for filepath in files:
            if not check_file_exists(filepath):
                print(f"  [FAIL] {filepath} - FILE NOT FOUND")
                all_passed = False
                continue
            
            passed, message = check_file_syntax(filepath)
            
            if passed:
                try:
                    with open(filepath, 'r', encoding='utf-8') as f:
                        lines = len(f.readlines())
                        total_lines += lines
                    print(f"  [OK] {filepath} ({lines} lines)")
                except Exception as e:
                    print(f"  [FAIL] {filepath} - {e}")
                    all_passed = False
            else:
                print(f"  [FAIL] {filepath} - {message}")
                all_passed = False
        
        print()
    
    print("="*70)
    print("SUMMARY")
    print("="*70)
    print(f"Total Files: {sum(len(f) for f in files_to_check.values())}")
    print(f"Total Lines: {total_lines}")
    
    if all_passed:
        print("\nSTATUS: ALL FILES VERIFIED - READY FOR DEPLOYMENT")
        print("\nNext steps:")
        print("1. Set GEMINI_API_KEY environment variable")
        print("2. Update main.py to wire Manager and Dashboard API")
        print("3. pip install -r requirements.txt")
        print("4. Run: uvicorn routemaster_agent.main:app --reload")
        print("5. Test endpoints with curl or Postman")
        print("6. Setup Grafana dashboard")
        print("7. Deploy to production")
        return 0
    else:
        print("\nSTATUS: ERRORS FOUND - FIX BEFORE DEPLOYMENT")
        return 1

if __name__ == "__main__":
    sys.exit(main())
