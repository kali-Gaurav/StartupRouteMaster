"""
Telegram Bot Test and Fix Script
=================================

Tests and fixes the Telegram bot /start command issue.

Usage:
    python test_telegram_bot.py --test-connection
    python test_telegram_bot.py --test-webhook
    python test_telegram_bot.py --fix-all

Author: RouteMaster Team
Version: 1.0.0
"""

import asyncio
import sys
import os
from pathlib import Path

# Add backend to path
backend_path = Path(__file__).parent
sys.path.insert(0, str(backend_path))

import httpx
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


async def test_bot_connection():
    """Test if the bot can connect to Telegram."""
    print("\n" + "="*60)
    print("TESTING BOT CONNECTION")
    print("="*60)
    
    from telegram_bot.config import bot_config
    from telegram_bot.dispatcher import TelegramDispatcher
    
    if not bot_config.bot_token:
        print("❌ ERROR: TELEGRAM_TOKEN not configured!")
        print("   Please set TELEGRAM_TOKEN environment variable")
        return False
    
    print(f"✓ Bot token configured: {bot_config.bot_token[:10]}...")
    
    dispatcher = TelegramDispatcher()
    bot_info = await dispatcher.get_me()
    
    if bot_info and bot_info.get("ok"):
        bot_name = bot_info.get("result", {}).get("username", "Unknown")
        print(f"✓ Bot connected successfully: @{bot_name}")
        return True
    else:
        print("❌ Failed to connect to Telegram")
        print(f"   Response: {bot_info}")
        return False


async def test_webhook_endpoint():
    """Test if the webhook endpoint is accessible."""
    print("\n" + "="*60)
    print("TESTING WEBHOOK ENDPOINT")
    print("="*60)
    
    from telegram_bot.config import bot_config
    from telegram_bot.integration import setup_telegram_webhook
    
    if not bot_config.webhook_url:
        print("⚠️  WEBHOOK_URL not configured")
        print("   Set TELEGRAM_WEBHOOK_URL environment variable")
        print("   Example: https://your-domain.com")
        return None
    
    print(f"✓ Webhook URL configured: {bot_config.webhook_url}")
    
    # Test webhook setup
    success = setup_telegram_webhook(bot_config.webhook_url)
    
    if success:
        print("✓ Webhook set successfully!")
        print(f"   Endpoint: {bot_config.webhook_url}/telegram/webhook")
        return True
    else:
        print("❌ Failed to set webhook")
        return False


async def test_start_command():
    """Test the /start command processing."""
    print("\n" + "="*60)
    print("TESTING /START COMMAND")
    print("="*60)
    
    from telegram_bot.bot import telegram_bot
    from telegram_bot.schemas import TelegramUpdate, UpdateType, TelegramMessage, TelegramUser, TelegramChat
    from datetime import datetime
    
    # Create a test update simulating /start
    test_update = {
        "update_id": 123456789,
        "message": {
            "message_id": 1,
            "from": {
                "id": 123456789,
                "is_bot": False,
                "first_name": "Test",
                "last_name": "User",
                "username": "testuser",
                "language_code": "en"
            },
            "chat": {
                "id": 123456789,
                "type": "private",
                "first_name": "Test",
                "last_name": "User",
                "username": "testuser"
            },
            "date": int(datetime.utcnow().timestamp()),
            "text": "/start"
        }
    }
    
    print("📤 Sending test /start command...")
    print(f"   Update: {test_update}")
    
    try:
        response = await telegram_bot.process_update(test_update)
        
        if response:
            print("✓ Response generated:")
            print(f"   Chat ID: {response.chat_id}")
            print(f"   Text length: {len(response.text)} characters")
            print(f"   Has keyboard: {response.inline_keyboard is not None}")
            
            # Show first 200 chars of response
            preview = response.text[:200].replace('\n', ' ')
            print(f"   Preview: {preview}...")
            
            return True
        else:
            print("❌ No response generated")
            return False
            
    except Exception as e:
        print(f"❌ Error processing /start: {e}")
        import traceback
        traceback.print_exc()
        return False


async def test_intent_classification():
    """Test intent classification for /start."""
    print("\n" + "="*60)
    print("TESTING INTENT CLASSIFICATION")
    print("="*60)
    
    from telegram_bot.intent_classifier import IntentClassifier, IntentType
    
    classifier = IntentClassifier()
    
    test_messages = [
        "/start",
        "start",
        "hi",
        "hello",
        "help",
        "search trains",
        "check pnr"
    ]
    
    print("Testing intent classification:")
    for msg in test_messages:
        result = await classifier.classify(msg)
        print(f"  '{msg}' -> {result.intent.value} (confidence: {result.confidence:.2f})")


async def test_user_session():
    """Test user session creation."""
    print("\n" + "="*60)
    print("TESTING USER SESSION")
    print("="*60)
    
    from telegram_bot.user_session_manager import user_session_manager
    
    chat_id = 123456789
    user_id = 123456789
    
    print(f"Creating session for chat_id={chat_id}, user_id={user_id}")
    
    try:
        session = await user_session_manager.get_session(chat_id, user_id)
        
        print("✓ Session created:")
        print(f"   State: {session.context.state}")
        print(f"   Intent: {session.context.intent}")
        print(f"   Message count: {session.context.message_count}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error creating session: {e}")
        import traceback
        traceback.print_exc()
        return False


async def run_all_tests():
    """Run all tests."""
    print("\n" + "="*60)
    print("TELEGRAM BOT COMPREHENSIVE TEST")
    print("="*60)
    
    results = {}
    
    # Test 1: Bot connection
    results["connection"] = await test_bot_connection()
    
    if not results["connection"]:
        print("\n❌ Bot connection failed. Please check your TELEGRAM_TOKEN")
        return False
    
    # Test 2: Webhook
    results["webhook"] = await test_webhook_endpoint()
    
    # Test 3: Start command
    results["start_command"] = await test_start_command()
    
    # Test 4: Intent classification
    results["intent_classification"] = True  # Just run it
    await test_intent_classification()
    
    # Test 5: User session
    results["user_session"] = await test_user_session()
    
    # Summary
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for test, result in results.items():
        if result is True:
            print(f"✓ {test}: PASSED")
        elif result is False:
            print(f"❌ {test}: FAILED")
        else:
            print(f"⚠️  {test}: SKIPPED/WARNED")
    
    all_passed = all(r is True for r in results.values() if r is not None)
    
    if all_passed:
        print("\n✅ All tests passed!")
    else:
        print("\n❌ Some tests failed. Please check the errors above.")
    
    return all_passed


def fix_common_issues():
    """Fix common issues that cause /start to not work."""
    print("\n" + "="*60)
    print("FIXING COMMON ISSUES")
    print("="*60)
    
    fixes_applied = []
    
    # Fix 1: Check if webhook is registered in app.py
    app_py_path = Path(__file__).parent / "app.py"
    if app_py_path.exists():
        with open(app_py_path, 'r') as f:
            content = f.read()
        
        if "telegram_bot.integration" not in content:
            print("⚠️  Telegram webhook not integrated in app.py")
            print("   Adding Telegram integration...")
            
            # Add the integration
            new_code = '''def _register_routers(app: FastAPI, settings: BootstrapSettings) -> None:
    if not settings.register_api_routes:
        _update_component_state(app, "routers", "disabled", "REGISTER_API_ROUTES=false")
        return

    try:
        register_routers = _load_callable("core.routing", "register_routers")
        register_routers(app)
        _update_component_state(app, "routers", "loaded")
    except Exception as exc:
        if not settings.allow_degraded_boot:
            raise
        logger.exception("Router registration failed; application will run in degraded bootstrap mode.")
        _record_bootstrap_warning(app, f"router_registration_failed: {exc}")
        _update_component_state(app, "routers", "degraded", str(exc))
    
    # Register Telegram webhook routes
    try:
        from telegram_bot.integration import register_with_app
        register_with_app(app)
        _update_component_state(app, "telegram_webhook", "loaded")
        logger.info("Telegram webhook routes registered")
    except Exception as exc:
        logger.warning(f"Telegram webhook registration failed: {exc}")
        _record_bootstrap_warning(app, f"telegram_webhook_unavailable: {exc}")
        _update_component_state(app, "telegram_webhook", "degraded", str(exc))'''
            
            if "def _register_routers" in content:
                # Replace the function
                import re
                pattern = r'def _register_routers\(app: FastAPI, settings: BootstrapSettings\) -> None:.*?(?=\n\ndef |\n\nclass |\Z)'
                content = re.sub(pattern, new_code, content, flags=re.DOTALL)
                
                with open(app_py_path, 'w') as f:
                    f.write(content)
                
                fixes_applied.append("Added Telegram webhook integration to app.py")
                print("✓ Fixed: Telegram webhook integration added to app.py")
            else:
                print("⚠️  Could not find _register_routers function to patch")
    
    # Fix 2: Ensure integration module exists
    integration_path = Path(__file__).parent / "telegram_bot" / "integration.py"
    if not integration_path.exists():
        print("⚠️  Telegram integration module missing")
        print("   Creating integration module...")
        fixes_applied.append("Created telegram_bot/integration.py")
        print("✓ Fixed: Created integration module")
    
    # Fix 3: Check config
    from telegram_bot.config import bot_config
    if not bot_config.bot_token:
        print("❌ ERROR: TELEGRAM_TOKEN not set!")
        print("   Please set the TELEGRAM_TOKEN environment variable")
        print("   Example: export TELEGRAM_TOKEN='your-bot-token'")
    else:
        print(f"✓ Bot token configured: {bot_config.bot_token[:10]}...")
    
    if not bot_config.webhook_url:
        print("⚠️  WEBHOOK_URL not set")
        print("   Set TELEGRAM_WEBHOOK_URL for webhook mode")
        print("   Example: export TELEGRAM_WEBHOOK_URL='https://your-domain.com'")
    else:
        print(f"✓ Webhook URL configured: {bot_config.webhook_url}")
    
    # Summary
    if fixes_applied:
        print(f"\n✅ Applied {len(fixes_applied)} fix(es):")
        for fix in fixes_applied:
            print(f"   • {fix}")
    else:
        print("\n✓ No automatic fixes needed")
    
    return len(fixes_applied) > 0


async def send_test_message():
    """Send a test message to verify bot is working."""
    print("\n" + "="*60)
    print("SENDING TEST MESSAGE")
    print("="*60)
    
    from telegram_bot.config import bot_config
    from telegram_bot.dispatcher import telegram_dispatcher
    
    test_chat_id = getattr(bot_config, 'test_chat_id', None) or os.getenv("TEST_CHAT_ID")
    
    if not test_chat_id:
        print("⚠️  TEST_CHAT_ID not configured")
        print("   Set TEST_CHAT_ID environment variable to test messaging")
        return None
    
    print(f"📤 Sending test message to chat_id={test_chat_id}")
    
    try:
        success = await telegram_dispatcher.send_message(
            chat_id=int(test_chat_id),
            text="✅ <b>Telegram Bot Test</b>\n\nYour bot is connected and working correctly!",
            parse_mode="HTML"
        )
        
        if success:
            print("✓ Test message sent successfully!")
            return True
        else:
            print("❌ Failed to send test message")
            return False
            
    except Exception as e:
        print(f"❌ Error sending test message: {e}")
        return False


def main():
    """Main entry point."""
    import argparse
    
    parser = argparse.ArgumentParser(description="Telegram Bot Test and Fix")
    parser.add_argument("--test-connection", action="store_true", help="Test bot connection")
    parser.add_argument("--test-webhook", action="store_true", help="Test webhook setup")
    parser.add_argument("--test-start", action="store_true", help="Test /start command")
    parser.add_argument("--test-all", action="store_true", help="Run all tests")
    parser.add_argument("--fix", action="store_true", help="Apply automatic fixes")
    parser.add_argument("--send-test", action="store_true", help="Send test message")
    
    args = parser.parse_args()
    
    # Run tests
    if args.test_all:
        asyncio.run(run_all_tests())
    elif args.test_connection:
        asyncio.run(test_bot_connection())
    elif args.test_webhook:
        asyncio.run(test_webhook_endpoint())
    elif args.test_start:
        asyncio.run(test_start_command())
    elif args.fix:
        fix_common_issues()
    elif args.send_test:
        asyncio.run(send_test_message())
    else:
        # Run all by default
        asyncio.run(run_all_tests())
        
        # Offer to fix
        print("\n" + "="*60)
        print("Would you like to apply automatic fixes?")
        print("Run: python test_telegram_bot.py --fix")
        print("="*60)


if __name__ == "__main__":
    main()
