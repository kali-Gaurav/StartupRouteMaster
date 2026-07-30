import asyncio
import os
import sys
import requests
import time
from dotenv import load_dotenv

# Ensure we can import from backend
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from telegram_bot.bot import telegram_bot

async def run_full_pipeline_test():
    load_dotenv()
    token = os.getenv('TELEGRAM_BOT_TOKEN')
    if not token:
        print("TELEGRAM_BOT_TOKEN not found in .env")
        return

    print("[TEST MODE] Starting full Telegram pipeline test...")
    print("Please send any message (like /start or 'hi') to your bot on Telegram now!")
    print("   (Make sure your main app.py is NOT running so we can catch the message here)")
    
    offset = 0
    message_caught = False
    
    # Poll for 60 seconds
    for _ in range(30):
        try:
            res = requests.get(f'https://api.telegram.org/bot{token}/getUpdates', params={'timeout': 2, 'offset': offset})
            data = res.json()
            
            if data.get('ok') and data.get('result'):
                updates = data['result']
                for update in updates:
                    message_caught = True
                    offset = update['update_id'] + 1
                    
                    print(f"\nCaught Message: {update.get('message', {}).get('text')}")
                    print("Processing through full TelegramBot NLP pipeline...")
                    
                    try:
                        # Feed it directly into the real backend pipeline
                        await telegram_bot.process_update(update)
                        print("Pipeline processed successfully! Check your Telegram for the bot's response.")
                    except Exception as e:
                        import traceback
                        print("Pipeline crashed during processing:")
                        traceback.print_exc()
                        
                if message_caught:
                    break
        except Exception as e:
            print(f"Error polling: {e}")
            
        time.sleep(2)
        
    if not message_caught:
        print("\nNo messages received within 60 seconds. Test finished.")

if __name__ == "__main__":
    # Force Windows to use SelectorEventLoop for httpx compatibility if needed
    if sys.platform == 'win32':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(run_full_pipeline_test())
