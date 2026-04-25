"""
Test API Endpoints and Router Functionality
"""
import asyncio
import sys
import os
from datetime import datetime
import logging

# Add backend to path
backend_path = os.path.abspath(os.path.dirname(__file__))
if backend_path not in sys.path:
    sys.path.insert(0, backend_path)

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class TestResults:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.warnings = 0
        self.results = []
    
    def add_pass(self, test_name, details=""):
        self.passed += 1
        result = {"test": test_name, "status": "PASS", "details": details}
        self.results.append(result)
        logger.info(f"✅ PASS: {test_name} {details}")
    
    def add_fail(self, test_name, error, details=""):
        self.failed += 1
        result = {"test": test_name, "status": "FAIL", "error": error, "details": details}
        self.results.append(result)
        logger.error(f"❌ FAIL: {test_name} - {error} {details}")
    
    def add_warning(self, test_name, warning):
        self.warnings += 1
        result = {"test": test_name, "status": "WARNING", "warning": warning}
        self.results.append(result)
        logger.warning(f"⚠️  WARNING: {test_name} - {warning}")
    
    def summary(self):
        return {
            "passed": self.passed,
            "failed": self.failed,
            "warnings": self.warnings,
            "total": self.passed + self.failed,
            "results": self.results
        }

async def test_api_routers():
    """Test API routers"""
    results = TestResults()
    logger.info("\n" + "="*60)
    logger.info("TESTING: API Routers")
    logger.info("="*60)
    
    # Test search router
    logger.info("\n--- Test: Search Router ---")
    try:
        from api.search import router as search_router
        results.add_pass("Search router import", f"Routes: {len(search_router.routes)}")
    except Exception as e:
        results.add_fail("Search router import", str(e))
    
    # Test stations router
    logger.info("\n--- Test: Stations Router ---")
    try:
        from api.stations import router as stations_router
        results.add_pass("Stations router import", f"Routes: {len(stations_router.routes)}")
    except Exception as e:
        results.add_fail("Stations router import", str(e))
    
    # Test trains router
    logger.info("\n--- Test: Trains Router ---")
    try:
        from api.status import router as trains_router
        results.add_pass("Trains/Status router import", f"Routes: {len(trains_router.routes)}")
    except Exception as e:
        results.add_fail("Trains/Status router import", str(e))
    
    # Test bookings router
    logger.info("\n--- Test: Bookings Router ---")
    try:
        from api.bookings import router as bookings_router
        results.add_pass("Bookings router import", f"Routes: {len(bookings_router.routes)}")
    except Exception as e:
        results.add_fail("Bookings router import", str(e))
    
    # Test payments router
    logger.info("\n--- Test: Payments Router ---")
    try:
        from api.payments import router as payments_router
        results.add_pass("Payments router import", f"Routes: {len(payments_router.routes)}")
    except Exception as e:
        results.add_fail("Payments router import", str(e))
    
    # Test admin router
    logger.info("\n--- Test: Admin Router ---")
    try:
        from api.admin import router as admin_router
        results.add_pass("Admin router import", f"Routes: {len(admin_router.routes)}")
    except Exception as e:
        results.add_fail("Admin router import", str(e))
    
    # Test user router
    logger.info("\n--- Test: User Router ---")
    try:
        from api.users import router as user_router
        results.add_pass("User router import", f"Routes: {len(user_router.routes)}")
    except Exception as e:
        results.add_fail("User router import", str(e))
    
    # Test auth router
    logger.info("\n--- Test: Auth Router ---")
    try:
        from api.auth import router as auth_router
        results.add_pass("Auth router import", f"Routes: {len(auth_router.routes)}")
    except Exception as e:
        results.add_fail("Auth router import", str(e))
    
    return results

async def test_utils():
    """Test utility modules"""
    results = TestResults()
    logger.info("\n" + "="*60)
    logger.info("TESTING: Utility Modules")
    logger.info("="*60)
    
    # Test station utils
    logger.info("\n--- Test: Station Utils ---")
    try:
        from utils.station_utils import resolve_stations, get_metro_group_codes
        results.add_pass("Station utils import", "Functions imported")
        
        # Test get_metro_group_codes
        codes = get_metro_group_codes("NDLS")
        results.add_pass("get_metro_group_codes", f"Codes for NDLS: {codes}")
    except Exception as e:
        results.add_fail("Station utils", str(e))
    
    # Test structured logging
    logger.info("\n--- Test: Structured Logging ---")
    try:
        from utils.structured_logging import setup_logging
        results.add_pass("Structured logging import", "setup_logging imported")
    except Exception as e:
        results.add_fail("Structured logging", str(e))
    
    # Test responses
    logger.info("\n--- Test: Responses Utils ---")
    try:
        from utils.responses import SafeJSONResponse
        results.add_pass("Responses import", "SafeJSONResponse imported")
    except Exception as e:
        results.add_fail("Responses import", str(e))
    
    # Test time utils
    logger.info("\n--- Test: Time Utils ---")
    try:
        from utils.time_utils import parse_time, format_duration
        results.add_pass("Time utils import", "Functions imported")
    except Exception as e:
        results.add_fail("Time utils import", str(e))
    
    # Test validation utils
    logger.info("\n--- Test: Validation Utils ---")
    try:
        from utils.validation import validate_pnr, validate_mobile
        results.add_pass("Validation utils import", "Functions imported")
    except Exception as e:
        results.add_fail("Validation utils import", str(e))
    
    return results

async def test_providers():
    """Test provider modules"""
    results = TestResults()
    logger.info("\n" + "="*60)
    logger.info("TESTING: Provider Modules")
    logger.info("="*60)
    
    # Test provider factory
    logger.info("\n--- Test: Provider Factory ---")
    try:
        from providers.factory import provider_factory
        results.add_pass("Provider factory import", "Factory imported")
        
        # Check registered providers
        providers = provider_factory.get_all_providers()
        results.add_pass("Provider factory", f"Providers: {list(providers.keys())}")
    except Exception as e:
        results.add_fail("Provider factory", str(e))
    
    # Test flight provider
    logger.info("\n--- Test: Flight Provider ---")
    try:
        from providers.flight_p import FlightProvider
        provider = FlightProvider()
        results.add_pass("Flight provider", f"Provider created: {provider.provider_id}")
    except Exception as e:
        results.add_fail("Flight provider", str(e))
    
    # Test bus provider
    logger.info("\n--- Test: Bus Provider ---")
    try:
        from providers.bus_provider import BusProvider
        provider = BusProvider()
        results.add_pass("Bus provider", f"Provider created: {provider.provider_id}")
    except Exception as e:
        results.add_fail("Bus provider", str(e))
    
    # Test taxi provider
    logger.info("\n--- Test: Taxi Provider ---")
    try:
        from providers.taxi_p import TaxiProvider
        provider = TaxiProvider()
        results.add_pass("Taxi provider", f"Provider created: {provider.provider_id}")
    except Exception as e:
        results.add_fail("Taxi provider", str(e))
    
    return results

async def test_nexus_modules():
    """Test Nexus modules"""
    results = TestResults()
    logger.info("\n" + "="*60)
    logger.info("TESTING: Nexus Modules")
    logger.info("="*60)
    
    # Test Nexus bootstrapper
    logger.info("\n--- Test: Nexus Bootstrapper ---")
    try:
        from core.nexus.bootstrapper import nexus_boot
        results.add_pass("Nexus bootstrapper", f"State: {nexus_boot.state}")
    except Exception as e:
        results.add_fail("Nexus bootstrapper", str(e))
    
    # Test Nexus governor
    logger.info("\n--- Test: Nexus Governor ---")
    try:
        from core.nexus.audit.governor import nexus_governor
        stats = await nexus_governor.get_stats()
        results.add_pass("Nexus governor", f"Throttle: {stats.get('throttle_factor', 0)}")
    except Exception as e:
        results.add_fail("Nexus governor", str(e))
    
    # Test Nexus triage
    logger.info("\n--- Test: Nexus Triage ---")
    try:
        from core.nexus.audit.triage import nexus_triage
        results.add_pass("Nexus triage", "Module imported")
    except Exception as e:
        results.add_fail("Nexus triage", str(e))
    
    # Test Nexus spine
    logger.info("\n--- Test: Nexus Spine ---")
    try:
        from core.nexus.spine import NeuralSpine
        NeuralSpine.initialize()
        results.add_pass("Nexus spine", "Spine initialized")
    except Exception as e:
        results.add_fail("Nexus spine", str(e))
    
    # Test Nexus topology
    logger.info("\n--- Test: Nexus Topology ---")
    try:
        from core.nexus.topology import NexusCartographer
        results.add_pass("Nexus topology", "Cartographer imported")
    except Exception as e:
        results.add_fail("Nexus topology", str(e))
    
    return results

async def main():
    """Run all tests"""
    logger.info("\n" + "="*80)
    logger.info("🚀 STARTING API & UTILITIES TEST SUITE")
    logger.info("="*80)
    
    all_results = {
        "api_routers": await test_api_routers(),
        "utils": await test_utils(),
        "providers": await test_providers(),
        "nexus_modules": await test_nexus_modules()
    }
    
    # Print summary
    logger.info("\n" + "="*80)
    logger.info("📊 TEST SUMMARY")
    logger.info("="*80)
    
    total_passed = 0
    total_failed = 0
    total_warnings = 0
    
    for module_name, results in all_results.items():
        summary = results.summary()
        total_passed += summary["passed"]
        total_failed += summary["failed"]
        total_warnings += summary["warnings"]
        
        logger.info(f"\n{module_name.upper()}:")
        logger.info(f"  ✅ Passed: {summary['passed']}")
        logger.info(f"  ❌ Failed: {summary['failed']}")
        logger.info(f"  ⚠️  Warnings: {summary['warnings']}")
        
        if summary["failed"] > 0:
            logger.info(f"\n  Failed tests:")
            for result in summary["results"]:
                if result["status"] == "FAIL":
                    logger.info(f"    - {result['test']}: {result.get('error', 'Unknown error')}")
    
    logger.info("\n" + "="*80)
    logger.info(f"OVERALL RESULTS:")
    logger.info(f"  ✅ Total Passed: {total_passed}")
    logger.info(f"  ❌ Total Failed: {total_failed}")
    logger.info(f"  ⚠️  Total Warnings: {total_warnings}")
    if (total_passed + total_failed) > 0:
        logger.info(f"  📈 Success Rate: {total_passed / (total_passed + total_failed) * 100:.1f}%")
    logger.info("="*80)
    
    return all_results

if __name__ == "__main__":
    results = asyncio.run(main())
    
    # Save results to file
    import json
    output = {
        "timestamp": datetime.now().isoformat(),
        "results": {k: v.summary() for k, v in results.items()}
    }
    
    with open("backend/test_api_results.json", "w") as f:
        json.dump(output, f, indent=2, default=str)
    
    logger.info(f"\n📄 Results saved to backend/test_api_results.json")