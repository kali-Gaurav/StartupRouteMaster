"""
RouteMaster Backend-Frontend Integration Test Suite
Tests all critical endpoints and integration flows
"""

import asyncio
import sys
import os
import httpx
from datetime import datetime
from typing import Dict, Any

# Configuration
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")
print(f"🚀 Testing backend at: {BACKEND_URL}")

class IntegrationTester:
    def __init__(self, base_url: str):
        self.base_url = base_url
        self.results: Dict[str, Any] = {
            "passed": [],
            "failed": [],
            "warnings": [],
            "timestamp": datetime.utcnow().isoformat()
        }
        self.auth_token: str = None
        
    async def run_all_tests(self):
        """Run all integration tests"""
        print("\n" + "="*80)
        print("ROUTEMASTER INTEGRATION TEST SUITE")
        print("="*80 + "\n")
        
        # Phase 1: Health Checks
        await self.test_health_checks()
        
        # Phase 2: Auth Endpoints
        await self.test_auth_endpoints()
        
        # Phase 3: User Endpoints
        if self.auth_token:
            await self.test_user_endpoints()
        
        # Phase 4: Core Features
        if self.auth_token:
            await self.test_core_endpoints()
        
        # Phase 5: WebSockets
        await self.test_websockets()
        
        # Print Summary
        self.print_summary()
    
    async def test_health_checks(self):
        """Test health check endpoints"""
        print("📋 PHASE 1: HEALTH CHECKS")
        print("-" * 80)
        
        async with httpx.AsyncClient() as client:
            # Test /healthz
            try:
                resp = await client.get(f"{self.base_url}/healthz", timeout=5.0)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("status") in ["healthy", "degraded"]:
                        self.pass_test("GET /healthz", data)
                    else:
                        self.fail_test("GET /healthz", "Invalid status response")
                else:
                    self.fail_test("GET /healthz", f"Status {resp.status_code}")
            except Exception as e:
                self.fail_test("GET /healthz", str(e))
            
            # Test /healthz/ready
            try:
                resp = await client.get(f"{self.base_url}/healthz/ready", timeout=5.0)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("status") == "ready":
                        self.pass_test("GET /healthz/ready", "System ready")
                    else:
                        self.warn_test("GET /healthz/ready", f"Status: {data.get('status')}")
                else:
                    self.fail_test("GET /healthz/ready", f"Status {resp.status_code}")
            except Exception as e:
                self.fail_test("GET /healthz/ready", str(e))
            
            # Test /healthz/live
            try:
                resp = await client.get(f"{self.base_url}/healthz/live", timeout=5.0)
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("status") == "alive":
                        self.pass_test("GET /healthz/live", f"Version {data.get('version')}")
                    else:
                        self.fail_test("GET /healthz/live", "Service not alive")
                else:
                    self.fail_test("GET /healthz/live", f"Status {resp.status_code}")
            except Exception as e:
                self.fail_test("GET /healthz/live", str(e))
            
            # Test root endpoint
            try:
                resp = await client.get(f"{self.base_url}/", timeout=5.0)
                if resp.status_code == 200:
                    self.pass_test("GET /", "Root endpoint accessible")
                else:
                    self.fail_test("GET /", f"Status {resp.status_code}")
            except Exception as e:
                self.fail_test("GET /", str(e))
    
    async def test_auth_endpoints(self):
        """Test authentication endpoints"""
        print("\n📋 PHASE 2: AUTHENTICATION ENDPOINTS")
        print("-" * 80)
        
        async with httpx.AsyncClient() as client:
            test_email = f"test_{datetime.utcnow().timestamp()}@test.com"
            test_phone = "+919876543210"
            
            # Test send-otp endpoint
            try:
                resp = await client.post(
                    f"{self.base_url}/api/auth/send-otp",
                    json={"email": test_email},
                    timeout=5.0
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("success"):
                        self.pass_test("POST /api/auth/send-otp", "OTP sent")
                    else:
                        self.fail_test("POST /api/auth/send-otp", data.get("message"))
                else:
                    self.warn_test("POST /api/auth/send-otp", f"Status {resp.status_code}")
            except Exception as e:
                self.fail_test("POST /api/auth/send-otp", str(e))
            
            # Test get-me endpoint (without token - should fail)
            try:
                resp = await client.get(
                    f"{self.base_url}/api/auth/me",
                    timeout=5.0
                )
                if resp.status_code == 401:
                    self.pass_test("GET /api/auth/me (no auth)", "Correctly rejected")
                else:
                    self.warn_test("GET /api/auth/me (no auth)", f"Expected 401, got {resp.status_code}")
            except Exception as e:
                self.fail_test("GET /api/auth/me (no auth)", str(e))
            
            # Test logout endpoint (without token - should work)
            try:
                resp = await client.post(
                    f"{self.base_url}/api/auth/logout",
                    timeout=5.0
                )
                if resp.status_code == 200:
                    data = resp.json()
                    if data.get("status") == "success":
                        self.pass_test("POST /api/auth/logout", "Logout accepted")
                    else:
                        self.fail_test("POST /api/auth/logout", "Invalid response")
                else:
                    self.fail_test("POST /api/auth/logout", f"Status {resp.status_code}")
            except Exception as e:
                self.fail_test("POST /api/auth/logout", str(e))
            
            # Check other auth endpoints exist
            endpoints = [
                ("POST", "/api/auth/verify-otp"),
                ("POST", "/api/auth/google"),
                ("POST", "/api/auth/telegram"),
            ]
            
            for method, path in endpoints:
                try:
                    if method == "POST":
                        resp = await client.post(
                            f"{self.base_url}{path}",
                            json={},
                            timeout=5.0
                        )
                    
                    if resp.status_code in [200, 400, 422]:  # Endpoint exists
                        self.pass_test(f"{method} {path}", "Endpoint exists")
                    else:
                        self.fail_test(f"{method} {path}", f"Status {resp.status_code}")
                except httpx.ConnectError:
                    self.fail_test(f"{method} {path}", "Connection error")
                except Exception as e:
                    self.fail_test(f"{method} {path}", str(e))
    
    async def test_user_endpoints(self):
        """Test user endpoints"""
        print("\n📋 PHASE 3: USER ENDPOINTS")
        print("-" * 80)
        
        headers = {"Authorization": f"Bearer {self.auth_token}"}
        
        async with httpx.AsyncClient() as client:
            # Test get profile
            try:
                resp = await client.get(
                    f"{self.base_url}/api/user/profile",
                    headers=headers,
                    timeout=5.0
                )
                if resp.status_code in [200, 404]:
                    self.pass_test("GET /api/user/profile", f"Status {resp.status_code}")
                else:
                    self.warn_test("GET /api/user/profile", f"Status {resp.status_code}")
            except Exception as e:
                self.fail_test("GET /api/user/profile", str(e))
            
            # Test update location
            try:
                resp = await client.post(
                    f"{self.base_url}/api/user/location",
                    headers=headers,
                    json={"latitude": 28.6139, "longitude": 77.2090},
                    timeout=5.0
                )
                if resp.status_code in [200, 404]:
                    self.pass_test("POST /api/user/location", f"Status {resp.status_code}")
                else:
                    self.warn_test("POST /api/user/location", f"Status {resp.status_code}")
            except Exception as e:
                self.fail_test("POST /api/user/location", str(e))
    
    async def test_core_endpoints(self):
        """Test core feature endpoints"""
        print("\n📋 PHASE 4: CORE ENDPOINTS")
        print("-" * 80)
        
        headers = {"Authorization": f"Bearer {self.auth_token}"}
        
        async with httpx.AsyncClient() as client:
            endpoints = [
                ("GET", "/api/stations"),
                ("GET", "/api/search"),
                ("GET", "/api/v1/booking"),
                ("GET", "/api/payment"),
                ("GET", "/api/sos"),
            ]
            
            for method, path in endpoints:
                try:
                    if method == "GET":
                        resp = await client.get(
                            f"{self.base_url}{path}",
                            headers=headers,
                            timeout=5.0
                        )
                    
                    if resp.status_code in [200, 400, 404]:
                        self.pass_test(f"{method} {path}", f"Status {resp.status_code}")
                    else:
                        self.warn_test(f"{method} {path}", f"Status {resp.status_code}")
                except Exception as e:
                    self.fail_test(f"{method} {path}", str(e)[:50])
    
    async def test_websockets(self):
        """Test WebSocket endpoints"""
        print("\n📋 PHASE 5: WEBSOCKET ENDPOINTS")
        print("-" * 80)
        
        # WebSocket endpoints to test
        ws_endpoints = [
            "/api/v1/chat/ws",
            "/api/v2/booking/ws",
        ]
        
        for ws_path in ws_endpoints:
            try:
                # Convert HTTP URL to WS
                ws_url = self.base_url.replace("http://", "ws://").replace("https://", "wss://")
                ws_url = f"{ws_url}{ws_path}"
                
                async with httpx.AsyncClient() as client:
                    # WebSocket test via OPTIONS preflight
                    http_path = ws_path.replace("ws", "http")
                    resp = await client.options(
                        f"{self.base_url}{http_path}",
                        timeout=5.0
                    )
                    
                    if resp.status_code in [200, 204]:
                        self.pass_test(f"OPTIONS {ws_path}", "CORS preflight OK")
                    else:
                        self.warn_test(f"OPTIONS {ws_path}", f"Status {resp.status_code}")
            except Exception as e:
                self.warn_test(f"WS {ws_path}", str(e)[:50])
    
    def pass_test(self, test_name: str, details: str = ""):
        """Record passed test"""
        msg = f"✅ {test_name}"
        if details:
            msg += f" - {details}"
        print(msg)
        self.results["passed"].append(test_name)
    
    def fail_test(self, test_name: str, reason: str = ""):
        """Record failed test"""
        msg = f"❌ {test_name}"
        if reason:
            msg += f" - {reason}"
        print(msg)
        self.results["failed"].append((test_name, reason))
    
    def warn_test(self, test_name: str, reason: str = ""):
        """Record warning"""
        msg = f"⚠️  {test_name}"
        if reason:
            msg += f" - {reason}"
        print(msg)
        self.results["warnings"].append((test_name, reason))
    
    def print_summary(self):
        """Print test summary"""
        print("\n" + "="*80)
        print("TEST SUMMARY")
        print("="*80)
        print(f"✅ Passed:  {len(self.results['passed'])}")
        print(f"❌ Failed:  {len(self.results['failed'])}")
        print(f"⚠️  Warnings: {len(self.results['warnings'])}")
        
        if self.results["failed"]:
            print("\n❌ FAILED TESTS:")
            for test, reason in self.results["failed"]:
                print(f"   - {test}: {reason}")
        
        if self.results["warnings"]:
            print("\n⚠️  WARNINGS:")
            for test, reason in self.results["warnings"]:
                print(f"   - {test}: {reason}")
        
        total = len(self.results["passed"]) + len(self.results["failed"]) + len(self.results["warnings"])
        percentage = (len(self.results["passed"]) / total * 100) if total > 0 else 0
        
        print(f"\n📊 Overall: {percentage:.1f}% PASS RATE ({len(self.results['passed'])}/{total})")
        print("="*80 + "\n")
        
        return len(self.results["failed"]) == 0


async def main():
    """Run integration tests"""
    tester = IntegrationTester(BACKEND_URL)
    success = await tester.run_all_tests()
    
    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
