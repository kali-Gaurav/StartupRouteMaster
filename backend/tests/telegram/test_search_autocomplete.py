import asyncio
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from telegram_bot.bot import telegram_bot
from telegram_bot.user_session_manager import user_session_manager
from core.lifespan_simple import lifespan
from fastapi import FastAPI

app = FastAPI()

async def test_autocomplete_gap():
    print("=== TEST 3: Station Auto-Complete (Zero Yield Analysis) ===")
    
    async with lifespan(app):
        # 1. Clear session
        await user_session_manager.clear_session(777)
        
        # 2. Simulate search with invalid/unrecognized stations
        update = {
            'update_id': 3001,
            'message': {
                'message_id': 3,
                'from': {'id': 777, 'is_bot': False, 'first_name': 'Tester'},
                'chat': {'id': 777, 'type': 'private'},
                'date': int(datetime.utcnow().timestamp()),
                'text': 'Train from Hogwarts to Narnia on 2026-05-15'
            }
        }
        
        print(f"Sending User Query: '{update['message']['text']}'")
        
        try:
            sent_messages = []
            async def mock_send_response(response):
                sent_messages.append(response)
                return True
            
            telegram_bot.dispatcher.send_response = mock_send_response
            
            await telegram_bot.process_update(update)
            
            if sent_messages:
                res = sent_messages[0]
                print("\nBot Responded With:")
                print(res.text.encode('ascii', 'ignore').decode())
            else:
                print("\nBot Failed to respond!")
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Pipeline Exception: {e}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_autocomplete_gap())
