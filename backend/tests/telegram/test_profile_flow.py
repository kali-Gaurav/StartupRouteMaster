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

async def test_profile_edit_gap():
    print("=== TEST 4: Passenger Profile Editing Flow ===")
    
    async with lifespan(app):
        # 1. Clear session
        await user_session_manager.clear_session(12345)
        
        # 2. Simulate User asking for Profile
        update_profile = {
            'update_id': 4001,
            'message': {
                'message_id': 4,
                'from': {'id': 12345, 'is_bot': False, 'first_name': 'Tester'},
                'chat': {'id': 12345, 'type': 'private'},
                'date': int(datetime.utcnow().timestamp()),
                'text': 'Show my profile'
            }
        }
        
        print(f"Sending User Query: '{update_profile['message']['text']}'")
        
        try:
            sent_messages = []
            async def mock_send_response(response):
                sent_messages.append(response)
                return True
            
            telegram_bot.dispatcher.send_response = mock_send_response
            telegram_bot.dispatcher.edit_message = mock_send_response
            
            # Request Profile
            await telegram_bot.process_update(update_profile)
            
            if sent_messages:
                res = sent_messages[-1]
                print("\nBot Responded With:")
                print(res.text.encode('ascii', 'ignore').decode())
            else:
                print("\nBot Failed to respond to Profile!")
                
            # 3. Simulate Clicking 'Edit Profile'
            update_edit = {
                'update_id': 4002,
                'callback_query': {
                    'id': 'cq_456',
                    'from': {'id': 12345, 'is_bot': False, 'first_name': 'Tester'},
                    'message': {
                        'message_id': 5,
                        'chat': {'id': 12345, 'type': 'private'},
                        'date': 1234567890
                    },
                    'data': 'profile_edit'
                }
            }
            
            print("\nSending Callback Query: 'profile_edit'")
            sent_messages.clear()
            
            # The router handles callbacks via bot.process_update too
            await telegram_bot.process_update(update_edit)
            
            if sent_messages:
                res = sent_messages[-1]
                print("\nBot Responded With:")
                print(res.text.encode('ascii', 'ignore').decode())
            else:
                print("\nBot Failed to respond to Edit Callback!")
                
        except Exception as e:
            import traceback
            traceback.print_exc()
            print(f"Pipeline Exception: {e}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_profile_edit_gap())
