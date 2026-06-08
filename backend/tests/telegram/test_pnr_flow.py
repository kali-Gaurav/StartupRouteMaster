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

class MockRedis:
    def __init__(self): self.data = {}
    async def get(self, key): return self.data.get(key)
    async def set(self, key, value, *args, **kwargs): self.data[key] = value

user_session_manager.redis = MockRedis()

async def test_pnr_flow_gap():
    print("=== TEST 5: PNR Status Flow with Missing Input ===")
    
    async with lifespan(app):
        chat_id = 54321
        await user_session_manager.clear_session(chat_id)
        
        # 1. User says "Check PNR" but gives NO number
        update_intent = {
            'update_id': 5001,
            'message': {
                'message_id': 6,
                'from': {'id': chat_id, 'is_bot': False, 'first_name': 'Tester'},
                'chat': {'id': chat_id, 'type': 'private'},
                'date': int(datetime.utcnow().timestamp()),
                'text': 'Check my PNR'
            }
        }
        
        print(f"Sending User Query: '{update_intent['message']['text']}'")
        
        try:
            sent_messages = []
            async def mock_send_response(response):
                sent_messages.append(response)
                return True
            
            telegram_bot.dispatcher.send_response = mock_send_response
            telegram_bot.dispatcher.edit_message = mock_send_response
            
            # Request check
            await telegram_bot.process_update(update_intent)
            
            if sent_messages:
                res = sent_messages[-1]
                print("\nBot Prompted With:")
                print(res.text.encode('ascii', 'ignore').decode())
            else:
                print("\nBot Failed to respond!")
                
            # 2. User provides the 10-digit number
            update_input = {
                'update_id': 5002,
                'message': {
                    'message_id': 7,
                    'from': {'id': chat_id, 'is_bot': False, 'first_name': 'Tester'},
                    'chat': {'id': chat_id, 'type': 'private'},
                    'date': int(datetime.utcnow().timestamp()),
                    'text': '1234567890'
                }
            }
            
            print(f"\nSending User Reply: '{update_input['message']['text']}'")
            sent_messages.clear()
            
            await telegram_bot.process_update(update_input)
            
            if sent_messages:
                res = sent_messages[-1]
                print("\nBot Responded With PNR Status:")
                print(res.text.encode('ascii', 'ignore').decode())
            else:
                print("\nBot Failed to respond to PNR input!")
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Pipeline Exception: {e}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_pnr_flow_gap())
