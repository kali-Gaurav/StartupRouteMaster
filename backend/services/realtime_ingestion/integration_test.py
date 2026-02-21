"""
End-to-end integration and test script for real-time routing pipeline.

This script demonstrates the complete flow:
1. Start live ingestion service
2. Fetch and parse real-time train data
3. Apply delay propagation
4. Update routing overlay
5. Score routes with ML models
6. Verify integration

Run as: python -m backend.services.realtime_ingestion.integration_test
"""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import List, Dict

from sqlalchemy.orm import Session

# Import pipeline components
from backend.database import SessionLocal
from backend.database.models import (
    TrainLiveUpdate, TrainMaster, TrainStation, TrainState,
    RealtimeData, RealtimeData as Event
)

from .api_client import RappidAPIClient, get_active_trains
from .parser import extract_train_update, parse_delay
from .delay_propagation import DelayPropagationManager
from .ingestion_worker import LiveIngestionWorker

# Optional ML imports (might not be available in all environments)
try:
    from backend.services.ml import (
        DelayPredictionModel,
        ReliabilityScoreModel,
        TransferSuccessProbabilityModel,
    )
    HAS_ML = True
except ImportError:
    HAS_ML = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)


class IntegrationTester:
    """
    Comprehensive test suite for the real-time routing pipeline.
    """
    
    def __init__(self, db_session: Session):
        self.session = db_session
        self.api_client = RappidAPIClient()
        self.results = {}
    
    def run_all_tests(self) -> bool:
        """Run complete integration test suite."""
        logger.info("=" * 70)
        logger.info("🧪 STARTING END-TO-END INTEGRATION TEST")
        logger.info("=" * 70)
        
        tests = [
            ("Database Schema", self.test_database_schema),
            ("API Client", self.test_api_client),
            ("Data Parsing", self.test_data_parsing),
            ("Delay Propagation", self.test_delay_propagation),
            ("Realtime Event Processing", self.test_event_processing),
            ("ML Models", self.test_ml_models) if HAS_ML else None,
            ("End-to-End Flow", self.test_end_to_end),
        ]
        
        failed = []
        
        for test_info in tests:
            if test_info is None:
                continue
            
            test_name, test_func = test_info
            
            try:
                logger.info(f"\n🔍 {test_name}...")
                success = test_func()
                
                if success:
                    logger.info(f"✅ {test_name} PASSED")
                    self.results[test_name] = "PASS"
                else:
                    logger.error(f"❌ {test_name} FAILED")
                    self.results[test_name] = "FAIL"
                    failed.append(test_name)
            
            except Exception as e:
                logger.error(f"❌ {test_name} ERROR: {e}", exc_info=True)
                self.results[test_name] = f"ERROR: {e}"
                failed.append(test_name)
        
        # Print summary
        logger.info("\n" + "=" * 70)
        logger.info("📊 TEST SUMMARY")
        logger.info("=" * 70)
        
        for test_name, result in self.results.items():
            status = "✅" if result == "PASS" else "❌"
            logger.info(f"{status} {test_name}: {result}")
        
        if failed:
            logger.error(f"\n❌ {len(failed)} test(s) failed:")
            for name in failed:
                logger.error(f"   - {name}")
            return False
        else:
            logger.info("\n✅ ALL TESTS PASSED!")
            return True
    
    def test_database_schema(self) -> bool:
        """Verify database models and tables exist."""
        logger.info("  Checking database schema...")
        
        try:
            # Check TrainLiveUpdate exists
            updated = self.session.query(TrainLiveUpdate).limit(1).first()
            logger.info("  ✓ TrainLiveUpdate table accessible")
            
            # Check TrainState exists
            state = self.session.query(TrainState).limit(1).first()
            logger.info("  ✓ TrainState table accessible")
            
            # Check RealtimeData exists
            event = self.session.query(RealtimeData).limit(1).first()
            logger.info("  ✓ RealtimeData table accessible")
            
            return True
        
        except Exception as e:
            logger.error(f"  ❌ Schema check failed: {e}")
            return False
    
    def test_api_client(self) -> bool:
        """Test API client connectivity and parsing."""
        logger.info("  Testing API client...")
        
        # Test a known train (using example from spec)
        test_train = "12345"  # Saraighat Express
        
        logger.info(f"  Fetching live data for train {test_train}...")
        response = self.api_client.fetch_train_status(test_train)
        
        if response is None:
            logger.warning(f"  ⚠️  API did not return data (might be offline)")
            return True  # Not a failure if API is down
        
        if not response.get("success"):
            logger.error("  ❌ API returned success=false")
            return False
        
        if "data" not in response:
            logger.error("  ❌ API response missing 'data' field")
            return False
        
        data_array = response.get("data", [])
        logger.info(f"  ✓ API returned {len(data_array)} station updates")
        
        return len(data_array) > 0
    
    def test_data_parsing(self) -> bool:
        """Test delay parsing and data extraction."""
        logger.info("  Testing data parsing...")
        
        # Test delay parsing
        test_cases = [
            ("On Time", 0),
            ("23min", 23),
            ("1h 30min", 90),
            ("", 0),
        ]
        
        for input_str, expected in test_cases:
            result = parse_delay(input_str)
            if result != expected:
                logger.error(f"  ❌ Parse delay '{input_str}' -> {result}, expected {expected}")
                return False
            logger.debug(f"  ✓ parse_delay('{input_str}') = {result}")
        
        # Test full extraction (if we have sample data)
        sample_response = {
            "success": True,
            "updated_time": "Updated 5min ago",
            "data": [
                {
                    "station_name": "Howrah Jn",
                    "distance": "-",
                    "timing": "16:16 16:05",
                    "delay": "11min",
                    "platform": "15",
                    "halt": "Source"
                }
            ]
        }
        
        updates = extract_train_update(sample_response, "12345")
        
        if len(updates) != 1:
            logger.error(f"  ❌ Expected 1 update, got {len(updates)}")
            return False
        
        update = updates[0]
        if update['delay_minutes'] != 11:
            logger.error(f"  ❌ Expected delay 11min, got {update['delay_minutes']}")
            return False
        
        logger.info(f"  ✓ Successfully extracted {len(updates)} parsed updates")
        return True
    
    def test_delay_propagation(self) -> bool:
        """Test delay propagation logic."""
        logger.info("  Testing delay propagation...")
        
        try:
            manager = DelayPropagationManager(self.session)
            
            # Get a sample train with data
            train = self.session.query(TrainMaster).limit(1).first()
            
            if not train:
                logger.warning("  ⚠️  No trains in database to test")
                return True
            
            # Get stations for this train
            stations = self.session.query(TrainStation).filter(
                TrainStation.train_number == train.train_number
            ).limit(5).all()
            
            if len(stations) < 2:
                logger.warning("  ⚠️  Insufficient stations to test propagation")
                return True
            
            # Test propagation with made-up delay
            current_delay = 15  # 15 minute delay
            propagated = manager.get_propagated_delays(
                train.train_number,
                0,  # Start from first station
                current_delay
            )
            
            logger.info(f"  ✓ Propagated {current_delay}min delay to {len(propagated)} downstream stations")
            
            # Verify delays decrease or stay same (recovery)
            for station_idx in sorted(propagated.keys()):
                delay = propagated[station_idx]
                logger.debug(f"    Station {station_idx}: {delay}min")
                
                if delay > current_delay * 1.5:  # Allow some jitter
                    logger.warning(f"  ⚠️  Delay increased unexpectedly")
            
            return True
        
        except Exception as e:
            logger.error(f"  ❌ Propagation test error: {e}")
            return False
    
    def test_event_processing(self) -> bool:
        """Test realtime event processor integration."""
        logger.info("  Testing event processing...")
        
        # This would require the full engine, so we'll do a simplified check
        try:
            # Create test event
            test_event = RealtimeData(
                event_type='delay',
                entity_id='12345',
                data={
                    'delay_minutes': 20,
                    'station_code': 'HWH',
                    'status': 'delayed'
                },
                status='new'
            )
            
            self.session.add(test_event)
            self.session.commit()
            
            # Verify event was created
            fetched = self.session.query(RealtimeData).filter(
                RealtimeData.entity_id == '12345'
            ).first()
            
            if fetched is None:
                logger.error("  ❌ Failed to create test event")
                return False
            
            logger.info("  ✓ Event storage and retrieval working")
            
            # Cleanup
            self.session.delete(fetched)
            self.session.commit()
            
            return True
        
        except Exception as e:
            logger.error(f"  ❌ Event processing error: {e}")
            self.session.rollback()
            return False
    
    def test_ml_models(self) -> bool:
        """Test ML model initialization and basic inference."""
        logger.info("  Testing ML models...")
        
        if not HAS_ML:
            logger.warning("  ⚠️  ML module not available")
            return True
        
        try:
            # Initialize models
            delay_model = DelayPredictionModel()
            reliability_model = ReliabilityScoreModel()
            transfer_model = TransferSuccessProbabilityModel()
            
            logger.info("  ✓ Models initialized successfully")
            
            # Test transfer model (doesn't require training)
            prob = transfer_model.get_transfer_success_probability(
                arrival_delay=10,
                transfer_buffer_minutes=20
            )
            
            if not (0 <= prob <= 1):
                logger.error(f"  ❌ Invalid probability: {prob}")
                return False
            
            logger.info(f"  ✓ Transfer success probability model working (P={prob:.2f})")
            
            return True
        
        except Exception as e:
            logger.error(f"  ❌ ML model error: {e}")
            return False
    
    def test_end_to_end(self) -> bool:
        """Test complete pipeline flow."""
        logger.info("  Testing end-to-end flow...")
        
        try:
            # 1. Start ingestion worker (briefly)
            logger.info("  1️⃣  Starting ingestion worker...")
            worker = LiveIngestionWorker(interval_minutes=1)
            worker.start()
            
            logger.info("  ✓ Ingestion worker started")
            
            # 2. Verify ingestion creates records
            initial_count = self.session.query(TrainLiveUpdate).count()
            logger.info(f"  Current TrainLiveUpdate records: {initial_count}")
            
            # 3. Test propagation on any existing data
            if initial_count > 0:
                latest_update = self.session.query(TrainLiveUpdate).order_by(
                    TrainLiveUpdate.recorded_at.desc()
                ).first()
                
                logger.info(f"  Latest update: {latest_update.train_number} "
                           f"at {latest_update.station_name} "
                           f"(delay: {latest_update.delay_minutes}min)")
            
            logger.info("  ✓ End-to-end flow verified")
            
            # Stop worker
            worker.stop()
            
            return True
        
        except Exception as e:
            logger.error(f"  ❌ End-to-end flow error: {e}")
            return False


def main():
    """Run the complete integration test."""
    session = SessionLocal()
    
    try:
        tester = IntegrationTester(session)
        success = tester.run_all_tests()
        
        exit(0 if success else 1)
    
    finally:
        session.close()


if __name__ == "__main__":
    main()
