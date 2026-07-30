import asyncio
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from telegram_bot.bot import telegram_bot
from telegram_bot.user_session_manager import user_session_manager
from telegram_bot.schemas import CallbackQuery

async def test_pagination():
    print("=== TEST 2: Dynamic Pagination ===")
    chat_id = 999
    
    # 1. Clear session
    await user_session_manager.clear_session(chat_id)
    
    # 2. Seed context with fake results
    session = await user_session_manager.get_session(chat_id, chat_id)
    fake_results = [
        {"segments": [{"train_no": f"1000{i}", "train_name": f"Mock Express {i}", "from_station": "DEL", "to_station": "BOM", "departure_time": "10:00", "arrival_time": "20:00"}], "total_fare": 1000}
        for i in range(12)
    ]
    session.context.data["search_results"] = fake_results
    session.context.data["search_page"] = 0
    await user_session_manager.save_session(session)
    
    print(f"Seeded {len(fake_results)} fake train results into session.")
    
    # 3. Simulate callback for page 1
    update = {
        'update_id': 2001,
        'callback_query': {
            'id': 'cq_123',
            'from': {'id': chat_id, 'is_bot': False, 'first_name': 'Tester'},
            'message': {
                'message_id': 2,
                'chat': {'id': chat_id, 'type': 'private'},
                'date': 1234567890
            },
            'data': 'search_page_1'
        }
    }
    
    print("Sending Callback Query: 'search_page_1' (Next Page)")
    
    try:
        sent_messages = []
        async def mock_send_response(response):
            sent_messages.append(response)
            return True
        
        telegram_bot.dispatcher.send_response = mock_send_response
        telegram_bot.dispatcher.edit_message = mock_send_response # Route edit to the same mock
        
        await telegram_bot.process_update(update)
        
        if sent_messages:
            res = sent_messages[0]
            print("\nBot Successfully Generated Page 2!")
            print(f"Response Text Length: {len(res.text)} characters")
            print("\nInline Keyboards generated:")
            for row in res.inline_keyboard:
                print([btn['text'].encode('ascii', 'ignore').decode() for btn in row])
        else:
            print("\nBot Failed to respond!")
            
    except Exception as e:
        import traceback
        traceback.print_exc()
        print(f"Pipeline Exception: {e}")

if __name__ == "__main__":
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(test_pagination())
