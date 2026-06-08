
import asyncio
import os
import sys
from datetime import datetime, timedelta
import json
import uuid
import hashlib

# Add current directory to sys.path
sys.path.append(os.getcwd())

from telegram_bot.bot import telegram_bot
from telegram_bot.user_session_manager import user_session_manager
from telegram_bot.schemas import TelegramMessage, UserState, IntentType
from telegram_bot.command_router import HandlerResult, HandlerResultStatus
from services.multi_layer_cache import multi_layer_cache
from telegram_bot.handlers.search_handler import SearchHandler
from core.lifespan_simple import lifespan
from fastapi import FastAPI

app = FastAPI()

class MockRedis:
    def __init__(self): self.data = {}
    async def get(self, key): return self.data.get(key)
    async def setex(self, key, ttl, value): self.data[key] = value
    async def set(self, key, value, *args, **kwargs): self.data[key] = value
    async def delete(self, key): self.data.pop(key, None)
    async def ping(self): return True
    def lock(self, *args, **kwargs): return self

async def test_pagination():
    print("=== TEST 7: Search Results Pagination & Callback ID Mapping ===")
    
    async with lifespan(app):
        multi_layer_cache.redis = MockRedis()
        
        chat_id = 112233
        await user_session_manager.clear_session(chat_id)
        
        # 1. Trigger Search (10 mock results)
        async def mock_search_trains_10(*args, **kwargs):
            return [
                {
                    "journey_id": f"train_{i}",
                    "train_number": f"1200{i}",
                    "train_name": f"Express {i}",
                    "segments": [
                        {
                            "train_number": f"1200{i}",
                            "train_name": f"Express {i}",
                            "from_station": "NDLS",
                            "to_station": "MMCT",
                            "departure_time": "2026-04-30T10:00:00",
                            "arrival_time": "2026-04-30T20:00:00"
                        }
                    ],
                    "total_duration": 600,
                    "total_fare": 500 + (i * 10)
                } for i in range(1, 11)
            ]
        
        original_search = SearchHandler._search_trains
        SearchHandler._search_trains = mock_search_trains_10
        
        # Mock message "train from Delhi to Mumbai tomorrow"
        update_1 = {
            "update_id": 1,
            "message": {
                "message_id": 1,
                "chat": {"id": chat_id, "type": "private"},
                "from": {"id": chat_id, "first_name": "Gaurav"},
                "text": "train from Delhi to Mumbai tomorrow",
                "date": int(datetime.utcnow().timestamp())
            }
        }
        
        sent_messages = []
        async def mock_send_response(response):
            sent_messages.append(response)
            return True
        
        async def mock_send_message(chat_id, text, reply_markup=None, **kwargs):
            from dataclasses import dataclass
            @dataclass
            class MockResponse:
                chat_id: int
                text: str
                inline_keyboard: list
            msg = MockResponse(chat_id=chat_id, text=text, inline_keyboard=inline_keyboard or kwargs.get("reply_markup"))
            sent_messages.append(msg)
            return {"message_id": len(sent_messages)}

        async def mock_edit_message(text, chat_id, message_id, inline_keyboard=None, **kwargs):
            sent_messages[-1].text = text
            sent_messages[-1].inline_keyboard = inline_keyboard or kwargs.get("reply_markup")
            return True

        telegram_bot.dispatcher.send_response = mock_send_response
        telegram_bot.dispatcher.send_message = mock_send_message
        telegram_bot.dispatcher.edit_message_text = mock_edit_message
        telegram_bot.dispatcher.answer_callback_query = lambda *args, **kwargs: asyncio.sleep(0)
        
        print("\nStep 1: User searches for trains")
        await telegram_bot.process_update(update_1)
        
        if sent_messages:
            res = sent_messages[-1]
            print(f"Bot Responded With (Page 1):\n{res.text.encode('ascii', 'ignore').decode()[:200]}...")
            
            # Verify Mapping
            session = await user_session_manager.get_session(chat_id, chat_id)
            id_map = session.context.data.get("id_map", {})
            print(f"ID Map Size: {len(id_map)}")
            
            # 2. Trigger Pagination (Next Page)
            print("\nStep 2: User clicks 'Next'")
            # Find 's_page_1' callback in keyboard
            callback_data = None
            for row in res.inline_keyboard:
                for btn in row:
                    if btn.get("callback_data") == "s_page_1":
                        callback_data = "s_page_1"
                        break
            
            if callback_data:
                update_2 = {
                    "update_id": 2,
                    "callback_query": {
                        "id": "1",
                        "from": {"id": chat_id},
                        "message": {
                            "message_id": 1,
                            "chat": {"id": chat_id, "type": "private"},
                            "text": res.text
                        },
                        "data": callback_data
                    }
                }
                await telegram_bot.process_update(update_2)
                
                # Verify Page 2
                session = await user_session_manager.get_session(chat_id, chat_id)
                print(f"Current Page: {session.context.data.get('search_page')}")
                
                if session.context.data.get('search_page') == 1:
                    print("PASSED: Pagination correctly updated state to 1")
                else:
                    print(f"FAILED: Expected page 1, got {session.context.data.get('search_page')}")
            else:
                print("FAILED: 'Next' button not found in keyboard")
                
            # 3. Verify Train Selection Callback Hashing
            print("\nStep 3: Verifying hashed train selection")
            # Get a short_id from the map
            short_id = list(id_map.keys())[0]
            full_jid = id_map[short_id]
            print(f"Mapping: {short_id} -> {full_jid}")
            
            callback_data_train = f"t_view_{short_id}"
            update_3 = {
                "update_id": 3,
                "callback_query": {
                    "id": "2",
                    "from": {"id": chat_id},
                    "message": {
                        "message_id": 1,
                        "chat": {"id": chat_id, "type": "private"}
                    },
                    "data": callback_data_train
                }
            }
            
            await telegram_bot.process_update(update_3)
            last_msg = sent_messages[-1]
            if f"Journey Details: {full_jid}" in last_msg.text:
                print("PASSED: Hashed ID correctly resolved to full Journey ID")
            else:
                print(f"FAILED: Journey ID not resolved. Bot said: {last_msg.text[:50]}")

        else:
            print("FAILED: Bot did not respond to search")

        SearchHandler._search_trains = original_search

if __name__ == "__main__":
    asyncio.run(test_pagination())
