import asyncio
import sys
from pathlib import Path
from datetime import datetime, timedelta, date

# Add backend to path
_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.append(str(_root))

from services.demand_forecaster import demand_forecaster

async def saturate():
    print("📈 Saturating demand for 12301 (NDLS-HWH) for next week...")
    
    travel_date = date.today() + timedelta(days=7)
    
    # Record 500 bookings for this segment to trigger 'OVERFLOW' or 'SURGE'
    # Default capacity for Rajdhani 3A is 64 * 6 = 384. 
    # 500 bookings will definitely trigger saturation.
    
    demand_forecaster.record_booking_event(
        train_number="12301",
        from_station="NDLS",
        to_station="HWH",
        travel_date=travel_date,
        count=500
    )
    
    forecast = await demand_forecaster.forecast_segment(
        train_number="12301",
        from_station="NDLS",
        to_station="HWH",
        travel_date=travel_date,
        class_code="3A"
    )
    
    print(f"✅ Forecast: Fill Rate {forecast.predicted_fill_rate}, Level: {forecast.demand_level}")
    print(f"Recommended Action: {forecast.recommended_action}")

if __name__ == "__main__":
    asyncio.run(saturate())
