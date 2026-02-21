import asyncio
import json
import logging
from datetime import datetime, timedelta
import sys
import os

# Adjust path to include the project root
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.database import SessionLocal
from backend.database.models import Stop, TrainStation, TrainLiveUpdate
from backend.services.emergency.alert_manager import EmergencyAlertManager

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def test_emergency_enrichment():
    session = SessionLocal()
    try:
        # 1. Setup Mock Railway Data for a "Live Train"
        train_no = "99999"
        
        # Cleanup
        session.query(Stop).filter(Stop.stop_id == "STN_SOS").delete()
        session.query(TrainStation).filter(TrainStation.train_number == train_no).delete()
        session.query(TrainLiveUpdate).filter(TrainLiveUpdate.train_number == train_no).delete()
        
        stn = Stop(stop_id="STN_SOS", code="STN_SOS", name="SOS Station", latitude=25.0, longitude=80.0)
        session.add(stn)
        
        # Departed STN_SOS 10 mins ago
        update = TrainLiveUpdate(
            train_number=train_no,
            station_code="STN_SOS",
            sequence=1,
            status="Departed",
            delay_minutes=0,
            recorded_at=datetime.utcnow() - timedelta(minutes=10)
        )
        session.add(update)
        
        # Schedule
        sched_1 = TrainStation(train_number=train_no, station_code="STN_SOS", sequence=1, distance_km=0)
        sched_2 = TrainStation(train_number=train_no, station_code="STN_NEXT", sequence=2, distance_km=50) # 50km away
        session.add_all([sched_1, sched_2])
        
        # Second station coords
        stn2 = Stop(stop_id="STN_NEXT", code="STN_NEXT", name="Next Station", latitude=26.0, longitude=81.0)
        session.add(stn2)
        
        session.commit()
        
        # 2. Simulate SOS Alert from a Passenger on this train
        raw_sos = {
            "id": "alert-123",
            "lat": 0, # GPS fail
            "lng": 0,
            "name": "Emergency User",
            "phone": "911",
            "trip": {
                "vehicle_number": train_no,
                "origin": "STN_SOS"
            }
        }
        
        logger.info("Step 1: Processing Raw SOS Alert...")
        alert_mgr = EmergencyAlertManager(session)
        enriched = await alert_mgr.process_sos_alert(raw_sos)
        
        # 3. Verify Enrichment
        if "railway_context" in enriched:
            logger.info("✅ SUCCESS: SOS Enriched with Railway Intelligence!")
            context = enriched["railway_context"]
            logger.info(f"   Estimated Pos: {enriched['lat']}, {enriched['lng']}")
            logger.info(f"   Next Station: {context['next_station']['name']}")
            logger.info(f"   Progress: {context['progress_percent']}%")
        else:
            logger.error("❌ FAILURE: No railway context found in enriched alert.")
            
        if enriched["lat"] != 0:
            logger.info("✅ SUCCESS: Interpolated lat replaced failed GPS.")

    finally:
        session.close()

if __name__ == "__main__":
    asyncio.run(test_emergency_enrichment())
