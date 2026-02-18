"""
Test script to verify Gemini API setup.

Run this script to verify:
1. .env file exists and is loaded
2. API keys are configured
3. Gemini client can be initialized
4. Configuration is correct

Usage:
    python test_gemini_setup.py
"""

import os
import sys
from pathlib import Path

# Fix encoding issues on Windows
if sys.platform == "win32":
    import io
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Add project root to path
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def test_env_file():
    """Test if .env file exists."""
    print("\n[1/4] Checking .env file...")
    env_file = project_root / ".env"
    
    if env_file.exists():
        print("✅ .env file found")
        return True
    else:
        print("❌ .env file NOT found")
        print(f"   Expected at: {env_file}")
        print("   Run: cp .env.example .env")
        return False


def test_dotenv_loading():
    """Test if python-dotenv can load .env file."""
    print("\n[2/4] Testing environment variable loading...")
    
    try:
        from dotenv import load_dotenv
        env_file = project_root / ".env"
        load_dotenv(env_file)
        print("✅ python-dotenv loaded successfully")
        return True
    except ImportError:
        print("❌ python-dotenv not installed")
        print("   Run: pip install python-dotenv")
        return False
    except Exception as e:
        print(f"❌ Error loading .env: {e}")
        return False


def test_gemini_config():
    """Test if Gemini configuration can be loaded."""
    print("\n[3/4] Checking Gemini configuration...")
    
    try:
        from routemaster_agent.config import GeminiConfig
        
        keys = GeminiConfig.get_api_keys()
        model = GeminiConfig.get_model()
        enabled = GeminiConfig.is_enabled()
        
        print(f"   API Keys configured: {len(keys)}")
        for i, key in enumerate(keys, 1):
            # Show only first 10 chars for security
            masked = key[:10] + "..." if len(key) > 10 else key
            print(f"   - Key {i}: {masked}")
        
        print(f"   Model: {model}")
        print(f"   Enabled: {enabled}")
        
        if enabled:
            print("✅ Gemini configuration loaded")
            return True
        else:
            print("❌ Gemini NOT enabled (no API keys found)")
            print("   Add keys to .env:")
            print("   GEMINI_API_KEY=your_key")
            print("   OR")
            print("   GEMINI_API_KEY1=key_1")
            print("   GEMINI_API_KEY2=key_2")
            return False
            
    except Exception as e:
        print(f"❌ Error loading Gemini config: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_gemini_client():
    """Test if GeminiClient can be initialized."""
    print("\n[4/4] Testing GeminiClient initialization...")
    
    try:
        from routemaster_agent.ai.gemini_client import GeminiClient
        
        client = GeminiClient()
        
        if client.enabled:
            print(f"✅ GeminiClient initialized successfully")
            print(f"   Model: {client.model}")
            print(f"   Keys available: {len(client.api_keys)}")
            return True
        else:
            print("⚠️  GeminiClient initialized but disabled (Gemini features unavailable)")
            print("   This is OK if you don't have API keys yet")
            return True  # Not a failure, just disabled
            
    except Exception as e:
        print(f"❌ Error initializing GeminiClient: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_all_configs():
    """Test all configuration modules."""
    print("\n[Bonus] Checking all configuration modules...")
    
    try:
        from routemaster_agent.config import (
            GeminiConfig,
            DatabaseConfig,
            ProxyConfig,
            RMAConfig,
            LoggingConfig,
            print_config
        )
        
        print("✅ All configuration modules loaded")
        print("\n" + "="*50)
        print_config()
        return True
        
    except Exception as e:
        print(f"⚠️  Could not load all configs: {e}")
        return False


def main():
    """Run all tests."""
    print("="*60)
    print("GEMINI API SETUP TEST")
    print("="*60)
    
    results = []
    
    # Run tests
    results.append(("ENV file exists", test_env_file()))
    results.append(("dotenv loading", test_dotenv_loading()))
    results.append(("Gemini config", test_gemini_config()))
    results.append(("GeminiClient init", test_gemini_client()))
    test_all_configs()
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:.<40} {status}")
    
    print("="*60)
    print(f"Result: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n✨ All tests passed! Your setup is correct.")
        print("\nNext steps:")
        print("1. Start using GeminiClient in your code")
        print("2. Check QUICK_START_GEMINI.md for usage examples")
        print("3. Monitor API usage at Google AI Studio")
        return 0
    else:
        print("\n⚠️  Some tests failed. See above for details.")
        print("\nTroubleshooting:")
        print("1. Check that .env file exists in project root")
        print("2. Verify .env has API keys configured")
        print("3. Run: pip install python-dotenv google-generativeai")
        print("4. See GEMINI_API_SETUP.md for detailed help")
        return 1


if __name__ == "__main__":
    exit_code = main()
    sys.exit(exit_code)
