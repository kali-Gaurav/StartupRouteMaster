import asyncio
from datetime import datetime, timedelta
import logging
from database.session import SessionLocal
from services.search_service import SearchService

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("test_pgt_kota")

async def test_search():
    db = SessionLocal()
    try:
        service = SearchService(db)
        
        # Calculate tomorrow's date
        tomorrow = datetime.now() + timedelta(days=1)
        date_str = tomorrow.strftime("%Y-%m-%d")
        
        logger.info(f"Searching routes from PGT to KOTA on {date_str}...")
        
        # The search service typically takes source code, destination code, and date
        # It maps to the SearchRequestSchema concepts
        # I'll call the core method directly or use the one exposed to the API.
        
        # Test 1: BUDGET Persona
        print("\n>>> TESTING PERSONA: BUDGET")
        res_budget = await service.search_routes(source="pgt", destination="kota", travel_date=date_str, budget_category="budget")
        top_budget = res_budget.get("grouped_journeys", {}).get("most_optimal", [])
        if top_budget:
            print(f"  Top Budget Route: {top_budget[0].get('journey_id')} | Fare: ₹{top_budget[0].get('total_fare')} | Score: {top_budget[0].get('score')}")

        # Test 2: EMERGENCY Persona
        print("\n>>> TESTING PERSONA: EMERGENCY")
        res_emergency = await service.search_routes(source="pgt", destination="kota", travel_date=date_str, budget_category="emergency")
        top_emergency = res_emergency.get("grouped_journeys", {}).get("most_optimal", [])
        if top_emergency:
            print(f"  Top Emergency Route: {top_emergency[0].get('journey_id')} | Fare: ₹{top_emergency[0].get('total_fare')} | Score: {top_emergency[0].get('score')}")

        # Comprehensive Output (using the latest request)
        grouped = res_emergency.get("grouped_journeys", {})
        
        def print_category(name, routes):
            print(f"\n>>> CATEGORY: {name.upper()} ({len(routes)} routes)")
            for i, r in enumerate(routes[:3]):
                print(f"  {i+1}. {r.get('journey_id')} | Fare: ₹{r.get('total_fare')} | Score: {r.get('score', 'N/A')}")

        print("\n=======================================================")
        print("🚆 COMPREHENSIVE ROUTE REPORT (PALAKKAD TO KOTA)")
        print("=======================================================")
        
        print_category("Top 3 Confirmed", grouped.get("top_3_confirmed", []))
        print_category("Direct", grouped.get("direct", []))
        print_category("One Transfer", grouped.get("one_transfer", []))
        print_category("Two+ Transfers", grouped.get("two_plus_transfer", []))
        print_category("Fastest", grouped.get("fastest", []))
        print_category("Most Optimal", grouped.get("most_optimal", []))

        # Check a specific route for pricing structure
        if res_emergency.get("journeys"):
            r = res_emergency["journeys"][0]
            p = r.get("pricing", {})
            print(f"\n[Price Audit] Ticket: ₹{p.get('ticket_fare')} | View: ₹{p.get('view_only_fee')} | Agent: ₹{p.get('agent_booking_fee')} | Total: ₹{p.get('total_agent_checkout')}")

        
    except Exception as e:
        logger.error(f"Test failed: {e}")
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_search())
