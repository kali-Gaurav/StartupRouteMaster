import asyncio
import os
import sys
from datetime import datetime, timedelta

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from telegram_bot.bot import telegram_bot
from telegram_bot.user_session_manager import user_session_manager
from telegram_bot.schemas import UserState
from core.lifespan_simple import lifespan
from fastapi import FastAPI

app = FastAPI()

class MockRedis:
    def __init__(self): self.data = {}
    async def get(self, key): return self.data.get(key)
    async def set(self, key, value, *args, **kwargs): self.data[key] = value
    async def delete(self, key): self.data.pop(key, None)

from services.multi_layer_cache import multi_layer_cache

from telegram_bot.handlers.search_handler import SearchHandler
async def mock_search_trains(*args, **kwargs):
    return [{"train_no": "12345", "name": "Test Express", "departure": "10:00", "arrival": "20:00", "duration": "10h", "classes": ["SL", "3A"]}]
SearchHandler._search_trains = mock_search_trains

async def test_search_fsm():
    print("=== TEST 6: Multi-turn Search FSM (Missing Date) ===")
    
    async with lifespan(app):
        # Set mock AFTER lifespan initializes (to prevent overwrite)
        multi_layer_cache.redis = MockRedis()
        
        chat_id = 998877
        await user_session_manager.clear_session(chat_id)
        
        # 1. User: "train from Delhi to Mumbai"
        update_1 = {
            'update_id': 6001,
            'message': {
                'message_id': 10,
                'from': {'id': chat_id, 'is_bot': False, 'first_name': 'FSM_Tester'},
                'chat': {'id': chat_id, 'type': 'private'},
                'date': int(datetime.utcnow().timestamp()),
                'text': 'train from Delhi to Mumbai'
            }
        }
        
        print(f"\nStep 1: User says '{update_1['message']['text']}'")
        
        sent_messages = []
        async def mock_send_response(response):
            sent_messages.append(response)
            return True
        
        telegram_bot.dispatcher.send_response = mock_send_response
        
        await telegram_bot.process_update(update_1)
        
        if sent_messages:
            res = sent_messages[-1]
            print(f"Bot Prompted With:\n{res.text.encode('ascii', 'ignore').decode()}")
            
            # Verify State
            session = await user_session_manager.get_session(chat_id, chat_id)
            print(f"Current State: {session.context.state}")
            
            if session.context.state != UserState.AWAITING_DATE:
                print("FAILED: Expected AWAITING_DATE state")
                return
        else:
            print("FAILED: Bot did not respond")
            return

        # 2. User: "tomorrow"
        update_2 = {
            'update_id': 6002,
            'message': {
                'message_id': 11,
                'from': {'id': chat_id, 'is_bot': False, 'first_name': 'FSM_Tester'},
                'chat': {'id': chat_id, 'type': 'private'},
                'date': int(datetime.utcnow().timestamp()),
                'text': 'tomorrow'
            }
        }
        
        print(f"\nStep 2: User says '{update_2['message']['text']}'")
        sent_messages.clear()
        
        await telegram_bot.process_update(update_2)
        
        if sent_messages:
            res = sent_messages[-1]
            print(f"Bot Responded With Results:\n{res.text[:200].encode('ascii', 'ignore').decode()}...")
            
            # Verify Search Data
            session = await user_session_manager.get_session(chat_id, chat_id)
            print(f"DEBUG: SM ID in test script: {id(user_session_manager)}")
            print(f"DEBUG: Full context.data in test script: {session.context.data}")
            print(f"Extracted Date: {session.context.data.get('search_date')}")
            
            if session.context.data.get('search_date') == (datetime.utcnow() + timedelta(days=1)).strftime("%Y-%m-%d"):
                print("PASSED: Multi-turn FSM logic verified.")
            else:
                print(f"FAILED: Date not correctly updated. Got {session.context.data.get('search_date')}")
        else:
            print("FAILED: Bot did not respond to 'tomorrow'")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_search_fsm())
