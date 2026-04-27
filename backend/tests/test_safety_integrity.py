
import sys
import os
import asyncio
from datetime import datetime, timedelta

# Add backend to path
sys.path.append(os.getcwd())

from database.session import SessionLocal, get_db
from database.models import User, Sathi, UserHeartbeat, SOSEvent, JourneyPlan
from services.agents.women_safety_agent import WomenSafetyAgent
from services.sos_service import SOSService



async def test_safety_logic():
    print("Starting Safety Integrity Verification...")
    
    # Initialize DB pools
    from database.session import initialize_database_pools
    await initialize_database_pools()
    
    db = SessionLocal()
    
    try:
        # 1. Setup Test Data
        # Create a test user
        test_user = db.query(User).filter(User.email == "safety_test@example.com").first()
        if not test_user:
            test_user = User(
                email="safety_test@example.com",
                full_name="Safety Test User",
                password_hash="dummy_hash",
                is_verified=True,
                role="user"
            )
            db.add(test_user)
            db.flush()
        
        # 2. Test WomenSafetyAgent
        print("\n--- Testing WomenSafetyAgent ---")
        agent = WomenSafetyAgent()
        await agent.on_start()
        
        # Mock route for assessment
        route_details = {
            "stations": [{"code": "NDLS"}, {"code": "GZB"}],
            "segments": [
                {"id": "seg1", "duration_minutes": 60, "train_type": "express", "coach_type": "ac3"}
            ],
            "travel_time": "23:30" # Night time
        }
        
        assessment = await agent.assess_route_safety(route_details)
        print(f"Route Safety Level: {assessment.get('safety_level')}")
        print(f"Safety Score: {assessment.get('overall_safety_score')}")
        
        # 3. Test SOS Heartbeat
        print("\n--- Testing SOS Heartbeat ---")
        sos_service = SOSService(db)
        journey_id = "test_journey_123"
        
        # Update heartbeat
        await sos_service.update_heartbeat(
            user_id=test_user.id,
            journey_id=journey_id,
            station_code="NDLS",
            next_eta=datetime.utcnow() - timedelta(minutes=45) # Overdue!
        )
        print("Heartbeat updated (set to overdue).")
        
        # Check for overdue
        print("Checking for overdue heartbeats...")
        await sos_service.check_overdue_heartbeats()
        
        # Verify SOS event was created
        sos_event = db.query(SOSEvent).filter(
            SOSEvent.user_id == test_user.id,
            SOSEvent.category == "MISSED_HEARTBEAT_AUTO"
        ).order_by(SOSEvent.triggered_at.desc()).first()
        
        if sos_event:
            print(f"SUCCESS: SOS Event auto-triggered for missed heartbeat (ID: {sos_event.id})")
        else:
            print("FAILURE: SOS Event NOT triggered for missed heartbeat")
            
        # 4. Test Sathi Discovery
        print("\n--- Testing Sathi Discovery ---")
        # Create a mock female Sathi
        test_sathi_user = db.query(User).filter(User.email == "female_sathi@example.com").first()
        if not test_sathi_user:
            test_sathi_user = User(
                email="female_sathi@example.com",
                full_name="Verified Female Sathi",
                password_hash="dummy_hash",
                is_verified=True,
                role="user"
            )
            db.add(test_sathi_user)
            db.flush()
            
        sathi = db.query(Sathi).filter(Sathi.user_id == test_sathi_user.id).first()
        if not sathi:
            sathi = Sathi(
                user_id=test_sathi_user.id,
                full_name="Verified Female Sathi",
                phone="9876543210",
                gender="female",
                verification_status="active",
                is_available=True,
                service_stations=["NDLS", "GZB"]
            )
            db.add(sathi)
            db.flush()
        
        sathi_results = await agent.find_female_sathis("NDLS")
        print(f"Sathis found at NDLS: {sathi_results.get('count')}")
        if sathi_results.get('count', 0) > 0:
            print("SUCCESS: Female Sathi discovery working.")
        else:
            print("FAILURE: Female Sathi NOT found at NDLS")
            
        db.commit()
        print("\nSafety Integrity Verification Complete.")
        
    except Exception as e:
        print(f"Error during test: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    asyncio.run(test_safety_logic())
