import asyncio
import json
import os
import sys
from datetime import date, datetime
from typing import Optional

# Setup imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from providers.clients.ntes_scraper import NtesScraperClient

from services.scraper_sentinel import scraper_sentinel
from database.session import initialize_database_pools

async def collect_train_data(train_no: str, journey_date: Optional[date] = None):
    """
    [Task 48.14] Standalone collector/scratchpad for NTES data.
    Saves the full station-wise schedule to data/scrapes/{train_no}_{date}.json
    """
    if not journey_date:
        journey_date = date.today()
        
    print(f"🔍 [SCRATCHPAD] Starting system boot...")
    await initialize_database_pools()
    await scraper_sentinel.start()
    
    print(f"🚀 [SCRATCHPAD] Starting collection for Train: {train_no} | Date: {journey_date}")
    
    client = NtesScraperClient()
    try:
        # 1. Execute Scrape
        data = await client.get_live_status(train_no, journey_date=journey_date)
        
        if not data:
            print(f"❌ [SCRATCHPAD] Failed to collect data for {train_no}. Check logs.")
            return

        # 2. Structure Data
        output_dir = "data/scrapes"
        os.makedirs(output_dir, exist_ok=True)
        
        filename = f"{output_dir}/{train_no}_{journey_date.isoformat()}.json"
        
        print(f"✅ [SCRATCHPAD] Successfully collected {len(data.get('full_table', []))} stations.")
        print(f"📍 [SCRATCHPAD] Current Station: {data.get('current_station')}")
        
        # 3. Save to JSON
        with open(filename, "w") as f:
            json.dump(data, f, indent=4)
            
        print(f"💾 [SCRATCHPAD] Data saved to {filename}")
        return data

    except Exception as e:
        print(f"💥 [SCRATCHPAD] Error during collection: {e}")
    finally:
        await client.close_playwright()

if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description="NTES Data Collector Scratchpad")
    parser.add_argument("train", help="Train number (e.g. 12625)")
    parser.add_argument("--date", help="Date in YYYY-MM-DD format (defaults to Today)")
    
    args = parser.parse_args()
    
    target_date = datetime.strptime(args.date, "%Y-%m-%d").date() if args.date else None
    
    asyncio.run(collect_train_data(args.train, target_date))
