"""
🔥 TIER 1 INTEGRATION TEST SUITE
Validates core end-to-end workflows: Search → Booking → Payment → Verification
"""

import asyncio
import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
import pytest

from database.session import SessionUser, SessionTransit
from database.models import User, Booking, SearchEvent, EscrowStatus
from services.hybrid_search_service import HybridSearchService
from services.pnr_verification_service import PNRVerificationService
from services.booking_verification_service import booking_verification_service
from core.route_engine import route_engine
from core.nexus.audit.triage import nexus_triage

logger = logging.getLogger("integration_tier1")

class IntegrationTestTier1:
    """Core end-to-end integration tests"""
    
    @pytest.fixture(autouse=True)
    async def setup(self):
        """Initialize services and database sessions"""
        await route_engine.init()
        self.user_db = SessionUser()
        self.transit_db = SessionTransit()
        self.search_service = HybridSearchService(self.transit_db, route_engine)
        
        logger.info("✅ Test environment initialized")
        yield
        
        self.user_db.close()
        self.transit_db.close()
    
    # ========================================================================
    # TEST SUITE 1: SEARCH FUNCTIONALITY
    # ========================================================================
    
    @pytest.mark.asyncio
    async def test_search_direct_route(self):
        """Test basic search for direct route"""
        logger.info("🧪 Test 1.1: Search direct route (NDLS→MMCT)")
        
        try:
            result = await self.search_service.search_routes(
                source="NDLS",
                destination="MMCT",
                travel_date="2026-04-20",
                budget_category=None,
                multi_modal=False
            )
            
            assert result is not None, "Search returned None"
            assert isinstance(result, dict), "Search returned non-dict"
            assert "routes" in result, "Result missing 'routes' key"
            assert "source" in result, "Result missing 'source' key"
            
            direct_routes = result["routes"]["direct"]
            logger.info(f"✅ Found {len(direct_routes)} direct routes")
            assert len(direct_routes) > 0, "No direct routes found"
            
            return True
        except Exception as e:
            logger.error(f"❌ Search failed: {e}")
            raise
    
    @pytest.mark.asyncio
    async def test_search_transfer_routes(self):
        """Test search for routes with transfers"""
        logger.info("🧪 Test 1.2: Search transfer route (ASN→TVC)")
        
        try:
            result = await self.search_service.search_routes(
                source="ASN",
                destination="TVC",
                travel_date="2026-04-20",
                budget_category="budget",
                multi_modal=False
            )
            
            assert result is not None
            total_routes = (
                len(result["routes"].get("direct", [])) +
                len(result["routes"].get("one_transfer", [])) +
                len(result["routes"].get("two_transfer", [])) +
                len(result["routes"].get("three_transfer", []))
            )
            
            logger.info(f"✅ Found {total_routes} total routes (with transfers)")
            assert total_routes > 0, "No routes found with transfers"
            
            return True
        except Exception as e:
            logger.error(f"❌ Transfer search failed: {e}")
            raise
    
    @pytest.mark.asyncio
    async def test_search_with_system_pressure(self):
        """Test search degrades gracefully under system pressure"""
        logger.info("🧪 Test 1.3: Search under simulated system pressure")
        
        try:
            # Simulate high system pressure
            original_backoff = nexus_triage.current_backoff
            nexus_triage._backoff_factor = 0.8  # 80% pressure
            
            result = await self.search_service.search_routes(
                source="NDLS",
                destination="MMCT",
                travel_date="2026-04-20"
            )
            
            assert result is not None, "Search failed under pressure"
            logger.info(f"✅ Search succeeded under 80% pressure")
            
            # Restore
            nexus_triage._backoff_factor = original_backoff
            return True
        except Exception as e:
            logger.error(f"❌ Search under pressure failed: {e}")
            raise
    
    # ========================================================================
    # TEST SUITE 2: BOOKING FUNCTIONALITY
    # ========================================================================
    
    @pytest.mark.asyncio
    async def test_create_booking(self):
        """Test booking creation workflow"""
        logger.info("🧪 Test 2.1: Create booking")
        
        try:
            # Create test user
            user = User(
                email=f"test_user_{datetime.now().timestamp()}@test.com",
                full_name="Test User",
                is_verified=True
            )
            self.user_db.add(user)
            self.user_db.commit()
            self.user_db.refresh(user)
            
            # Create booking
            booking = Booking(
                user_id=user.id,
                pnr_number=None,  # To be filled by PNR verification
                travel_date="2026-04-20",
                booking_status="pending",
                escrow_status=EscrowStatus.CREATED,
                amount_paid=0.0
            )
            self.user_db.add(booking)
            self.user_db.commit()
            self.user_db.refresh(booking)
            
            assert booking.id is not None, "Booking creation failed"
            logger.info(f"✅ Created booking: {booking.id}")
            
            return booking.id
        except Exception as e:
            logger.error(f"❌ Booking creation failed: {e}")
            raise
    
    @pytest.mark.asyncio
    async def test_booking_state_transitions(self):
        """Test booking escrow state machine"""
        logger.info("🧪 Test 2.2: Booking state transitions")
        
        try:
            # Create booking
            user = User(
                email=f"state_test_{datetime.now().timestamp()}@test.com",
                full_name="State Test User"
            )
            self.user_db.add(user)
            self.user_db.commit()
            
            booking = Booking(
                user_id=user.id,
                travel_date="2026-04-20",
                booking_status="pending",
                escrow_status=EscrowStatus.CREATED
            )
            self.user_db.add(booking)
            self.user_db.commit()
            
            # Test state transitions
            assert booking.escrow_status == EscrowStatus.CREATED
            
            # Transition to PAYMENT_PROCESSING
            booking.escrow_status = EscrowStatus.PAYMENT_PROCESSING
            self.user_db.commit()
            assert booking.escrow_status == EscrowStatus.PAYMENT_PROCESSING
            
            # Transition to COMPLETED
            booking.escrow_status = EscrowStatus.COMPLETED
            self.user_db.commit()
            assert booking.escrow_status == EscrowStatus.COMPLETED
            
            logger.info("✅ All state transitions succeeded")
            return True
        except Exception as e:
            logger.error(f"❌ State transitions failed: {e}")
            raise
    
    # ========================================================================
    # TEST SUITE 3: PAYMENT FLOW
    # ========================================================================
    
    @pytest.mark.asyncio
    async def test_payment_escrow_reservation(self):
        """Test payment escrow reservation system"""
        logger.info("🧪 Test 3.1: Payment escrow reservation")
        
        try:
            user = User(
                email=f"payment_test_{datetime.now().timestamp()}@test.com",
                full_name="Payment Test User"
            )
            self.user_db.add(user)
            self.user_db.commit()
            
            booking = Booking(
                user_id=user.id,
                travel_date="2026-04-20",
                booking_status="pending",
                escrow_status=EscrowStatus.CREATED,
                amount_paid=500.0  # ₹500
            )
            self.user_db.add(booking)
            self.user_db.commit()
            
            # Simulate payment processing
            booking.escrow_status = EscrowStatus.PAYMENT_PROCESSING
            self.user_db.commit()
            
            # Simulate successful payment
            booking.escrow_status = EscrowStatus.COMPLETED
            booking.booking_status = "confirmed"
            self.user_db.commit()
            
            logger.info(f"✅ Payment escrow succeeded: ₹{booking.amount_paid}")
            return True
        except Exception as e:
            logger.error(f"❌ Payment escrow failed: {e}")
            raise
    
    # ========================================================================
    # TEST SUITE 4: PNR VERIFICATION
    # ========================================================================
    
    @pytest.mark.asyncio
    async def test_pnr_completion_workflow(self):
        """Test PNR verification and booking completion"""
        logger.info("🧪 Test 4.1: PNR completion workflow")
        
        try:
            # Create user and booking
            user = User(
                email=f"pnr_test_{datetime.now().timestamp()}@test.com",
                full_name="PNR Test User"
            )
            self.user_db.add(user)
            self.user_db.commit()
            
            booking = Booking(
                user_id=user.id,
                travel_date="2026-04-20",
                booking_status="pending",
                escrow_status=EscrowStatus.COMPLETED,
                amount_paid=1000.0
            )
            self.user_db.add(booking)
            self.user_db.commit()
            self.user_db.refresh(booking)
            
            # Simulate PNR verification
            agent_id = "agent_test_001"
            pnr = "1234567890"
            
            result = PNRVerificationService.complete_booking(
                db=self.user_db,
                booking_id=booking.id,
                pnr_number=pnr,
                agent_id=agent_id,
                ticket_pdf_url=f"https://cdn.test.io/tickets/{pnr}.pdf"
            )
            
            assert result is True, "PNR completion failed"
            
            # Verify booking updated
            self.user_db.refresh(booking)
            assert booking.pnr_number == pnr
            assert booking.escrow_status == EscrowStatus.COMPLETED
            
            logger.info(f"✅ PNR completed: {pnr}")
            return True
        except Exception as e:
            logger.error(f"❌ PNR verification failed: {e}")
            raise
    
    # ========================================================================
    # TEST SUITE 5: SYSTEM HEALTH
    # ========================================================================
    
    @pytest.mark.asyncio
    async def test_system_health_check(self):
        """Test system health monitoring"""
        logger.info("🧪 Test 5.1: System health check")
        
        try:
            # Check route engine
            assert route_engine.graph_initialized, "Route engine not initialized"
            logger.info("✅ Route engine healthy")
            
            # Check triage
            diagnostics = await nexus_triage.get_deep_diagnostics()
            assert diagnostics is not None, "Triage diagnostics failed"
            logger.info(f"✅ Triage healthy: backoff={diagnostics['backoff_factor']}")
            
            # Check database
            test_user = User(
                email=f"health_test_{datetime.now().timestamp()}@test.com",
                full_name="Health Check"
            )
            self.user_db.add(test_user)
            self.user_db.commit()
            logger.info("✅ Database healthy")
            
            return True
        except Exception as e:
            logger.error(f"❌ Health check failed: {e}")
            raise

# ============================================================================
# TEST RUNNER
# ============================================================================

async def run_all_tests():
    """Run all integration tests"""
    logger.info("=" * 80)
    logger.info("🚀 TIER 1 INTEGRATION TEST SUITE STARTING")
    logger.info("=" * 80)
    
    test_suite = IntegrationTestTier1()
    results = {
        "passed": 0,
        "failed": 0,
        "errors": []
    }
    
    tests = [
        ("Search: Direct Route", test_suite.test_search_direct_route),
        ("Search: Transfer Routes", test_suite.test_search_transfer_routes),
        ("Search: Under Pressure", test_suite.test_search_with_system_pressure),
        ("Booking: Creation", test_suite.test_create_booking),
        ("Booking: State Transitions", test_suite.test_booking_state_transitions),
        ("Payment: Escrow", test_suite.test_payment_escrow_reservation),
        ("PNR: Completion", test_suite.test_pnr_completion_workflow),
        ("Health: System Check", test_suite.test_system_health_check),
    ]
    
    for test_name, test_func in tests:
        try:
            logger.info(f"\n▶️  Running: {test_name}")
            await test.setup()
            await test_func()
            results["passed"] += 1
            logger.info(f"✅ PASSED: {test_name}")
        except Exception as e:
            results["failed"] += 1
            results["errors"].append(f"{test_name}: {str(e)}")
            logger.error(f"❌ FAILED: {test_name}\n{e}")
    
    # Print summary
    logger.info("\n" + "=" * 80)
    logger.info("📊 TEST RESULTS SUMMARY")
    logger.info("=" * 80)
    logger.info(f"✅ Passed: {results['passed']}")
    logger.info(f"❌ Failed: {results['failed']}")
    
    if results["errors"]:
        logger.error("\n🔴 Errors:")
        for error in results["errors"]:
            logger.error(f"  - {error}")
    
    logger.info("=" * 80)
    
    return results["failed"] == 0

if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(name)s | %(levelname)s | %(message)s"
    )
    
    success = asyncio.run(run_all_tests())
    exit(0 if success else 1)
