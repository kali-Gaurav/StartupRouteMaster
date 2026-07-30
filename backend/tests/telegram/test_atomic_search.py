import asyncio
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from telegram_bot.bot import telegram_bot
from telegram_bot.user_session_manager import user_session_manager

async def test_search_gap_analysis():
    print("=== TEST 1: Missing Date Logic ===")
    
    # 1. Clear session to start fresh
    await user_session_manager.clear_session(888)
    
    # 2. Simulate incomplete search
    update = {
        'update_id': 1001,
        'message': {
            'message_id': 1,
            'from': {'id': 888, 'is_bot': False, 'first_name': 'Tester'},
            'chat': {'id': 888, 'type': 'private'},
            'date': int(datetime.utcnow().timestamp()),
            'text': 'Train from Delhi to Mumbai'
        }
    }
    
    print(f"Sending User Query: '{update['message']['text']}'")
    
    try:
        # We need to monkeypatch send_response so we can inspect what it sends
        sent_messages = []
        async def mock_send_response(response):
            sent_messages.append(response)
            return True
        
        telegram_bot.dispatcher.send_response = mock_send_response
        
        # Execute Pipeline
        await telegram_bot.process_update(update)
        
        # Check Response
        if sent_messages:
            print("\nBot Responded With:")
            print(f"Text: {sent_messages[0].text}")
        else:
            print("\nBot Failed to respond (Silent Error)!")
            
        # Check Session State
        session = await user_session_manager.get_session(888, 888)
        print(f"\nFinal State Machine state: {session.context.state}")
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Pipeline Exception: {e}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_search_gap_analysis())
