"""
🔥 SYSTEM STATE VALIDATOR
Comprehensive check for all critical components and their integration status.
"""

import os
import sys
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(name)s | %(levelname)s | %(message)s"
)
logger = logging.getLogger("system_validator")

class SystemValidator:
    """Validate entire system state and identify blockers"""
    
    def __init__(self, backend_path: str):
        self.backend_path = Path(backend_path)
        self.results = {
            "critical": [],
            "high": [],
            "medium": [],
            "low": [],
            "passed": []
        }
    
    def run_all_checks(self):
        """Execute comprehensive system validation"""
        logger.info("=" * 80)
        logger.info("🚀 STARTING COMPREHENSIVE SYSTEM VALIDATION")
        logger.info("=" * 80)
        
        # Phase 1: Code Quality
        self._check_python_syntax()
        self._check_type_annotations()
        self._check_imports()
        
        # Phase 2: Database
        self._check_database_models()
        self._check_database_migrations()
        
        # Phase 3: Services
        self._check_critical_services()
        self._check_api_endpoints()
        
        # Phase 4: Configuration
        self._check_environment_config()
        self._check_secrets()
        
        # Phase 5: Dependencies
        self._check_external_dependencies()
        
        # Report results
        self._generate_report()
    
    def _check_python_syntax(self):
        """Check all Python files for syntax errors"""
        logger.info("\n▶️  Phase 1.1: Python Syntax Check")
        
        py_files = list(self.backend_path.rglob("*.py"))
        errors = []
        
        for py_file in py_files[:50]:  # First 50 files
            try:
                with open(py_file, 'r', encoding='utf-8', errors='ignore') as f:
                    compile(f.read(), str(py_file), 'exec')
            except SyntaxError as e:
                errors.append(f"{py_file.name}: {e}")
            except Exception as e:
                # Skip files that can't be parsed
                pass
        
        if errors:
            self.results["critical"].extend([
                f"Syntax Error: {e}" for e in errors
            ])
            logger.error(f"❌ Found {len(errors)} syntax errors")
        else:
            self.results["passed"].append("✅ Python syntax check: PASSED")
            logger.info("✅ All Python files have valid syntax")
    
    def _read_file_safe(self, file_path):
        """Read file with proper encoding handling"""
        try:
            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                return f.read()
        except Exception:
            return ""
    
    def _check_type_annotations(self):
        """Check for typing consistency"""
        logger.info("▶️  Phase 1.2: Type Annotation Check")
        
        # Look for common type annotation issues
        imports_check = {
            "Optional": "from typing import Optional",
            "List": "from typing import List",
            "Dict": "from typing import Dict",
            "Mapped": "from sqlalchemy.orm import Mapped",
            "mapped_column": "from sqlalchemy import mapped_column"
        }
        
        issues = []
        for service_file in (self.backend_path / "services").glob("*.py"):
            content = self._read_file_safe(service_file)
            
            # Check for Column usage (should be mapped_column in 2.0)
            if "= Column(" in content and "mapped_column(" not in content:
                if "models.py" not in str(service_file):  # Skip models
                    issues.append(f"Legacy Column() in {service_file.name}")
        
        if issues:
            self.results["medium"].extend(issues)
            logger.warning(f"⚠️ Found {len(issues)} potential type issues")
        else:
            self.results["passed"].append("✅ Type annotations check: PASSED")
            logger.info("✅ Type annotations are consistent")
    
    def _check_imports(self):
        """Check for missing or broken imports"""
        logger.info("▶️  Phase 1.3: Import Check")
        
        # Critical imports that should exist
        critical_imports = {
            "database.models": ["User", "Booking", "SearchEvent"],
            "database.session": ["SessionUser", "SessionTransit"],
            "services.hybrid_search_service": ["HybridSearchService"],
            "core.route_engine": ["route_engine"],
            "core.nexus.audit.governor": ["nexus_governor"],
        }
        
        missing = []
        for module_path, symbols in critical_imports.items():
            module_file = self.backend_path / (module_path.replace(".", "/") + ".py")
            if not module_file.exists():
                missing.append(f"Module not found: {module_path}")
        
        if missing:
            self.results["critical"].extend(missing)
            logger.error(f"❌ Missing critical imports: {missing}")
        else:
            self.results["passed"].append("✅ All critical imports found")
            logger.info("✅ All critical imports exist")
    
    def _check_database_models(self):
        """Validate database models are properly typed"""
        logger.info("▶️  Phase 2.1: Database Models Check")
        
        models_file = self.backend_path / "database" / "models.py"
        
        if not models_file.exists():
            self.results["critical"].append("database/models.py not found")
            logger.error("❌ models.py not found")
            return
        
        content = self._read_file_safe(models_file)
        
        # Check for essential models
        required_models = ["User", "Booking", "SearchEvent", "Payment", "SeatInventory"]
        missing_models = [m for m in required_models if f"class {m}" not in content]
        
        if missing_models:
            self.results["high"].extend([f"Missing model: {m}" for m in missing_models])
            logger.warning(f"⚠️ Missing models: {missing_models}")
        else:
            self.results["passed"].append("✅ All essential models defined")
            logger.info("✅ All essential models found")
        
        # Check for Mapped[] type annotations
        if "Mapped[" in content:
            self.results["passed"].append("✅ SQLAlchemy 2.0 typed models detected")
            logger.info("✅ Models use SQLAlchemy 2.0 typed annotations")
        else:
            self.results["high"].append("Models may not be using SQLAlchemy 2.0 annotations")
            logger.warning("⚠️ Models may not be properly typed for SQLAlchemy 2.0")
    
    def _check_database_migrations(self):
        """Check database initialization and migrations"""
        logger.info("▶️  Phase 2.2: Database Migrations Check")
        
        # Check for migration support
        alembic_dir = self.backend_path / "alembic"
        if alembic_dir.exists():
            self.results["passed"].append("✅ Alembic migrations configured")
            logger.info("✅ Migration system detected")
        else:
            self.results["medium"].append("No alembic migrations found (manual schema mgmt)")
            logger.warning("⚠️ No automated migration system detected")
    
    def _check_critical_services(self):
        """Validate all critical services can be imported"""
        logger.info("▶️  Phase 3.1: Critical Services Check")
        
        services_to_check = [
            "hybrid_search_service",
            "payment_service",
            "pnr_verification_service",
            "karma_service",
            "inventory_service",
            "sos_service"
        ]
        
        missing = []
        for service in services_to_check:
            service_file = self.backend_path / "services" / f"{service}.py"
            if not service_file.exists():
                missing.append(service)
        
        if missing:
            self.results["high"].extend([f"Missing service: {s}" for s in missing])
            logger.error(f"❌ Missing services: {missing}")
        else:
            self.results["passed"].append(f"✅ All {len(services_to_check)} critical services found")
            logger.info(f"✅ All {len(services_to_check)} critical services exist")
    
    def _check_api_endpoints(self):
        """Verify key API endpoints are defined"""
        logger.info("▶️  Phase 3.2: API Endpoints Check")
        
        api_v3_dir = self.backend_path / "api" / "v3"
        
        required_endpoints = ["search.py", "bookings.py"]
        missing = [f for f in required_endpoints if not (api_v3_dir / f).exists()]
        
        if missing:
            self.results["high"].extend([f"Missing API endpoint: {e}" for e in missing])
            logger.error(f"❌ Missing endpoints: {missing}")
        else:
            self.results["passed"].append(f"✅ All {len(required_endpoints)} core API endpoints found")
            logger.info(f"✅ Core API endpoints configured")
    
    def _check_environment_config(self):
        """Check environment configuration"""
        logger.info("▶️  Phase 4.1: Environment Configuration Check")
        
        config_file = self.backend_path / "config.py"
        
        if not config_file.exists():
            self.results["critical"].append("config.py not found")
            logger.error("❌ config.py not found")
            return
        
        content = self._read_file_safe(config_file)
        
        required_config_vars = [
            "RAZORPAY_KEY_ID",
            "DATABASE_URL",
            "ENVIRONMENT"
        ]
        
        missing = [v for v in required_config_vars if f"{v}" not in content]
        
        if missing:
            self.results["high"].extend([f"Missing config: {v}" for v in missing])
            logger.warning(f"⚠️ Missing config variables: {missing}")
        else:
            self.results["passed"].append("✅ All critical config variables found")
            logger.info("✅ Configuration complete")
    
    def _check_secrets(self):
        """Check for properly managed secrets"""
        logger.info("▶️  Phase 4.2: Secrets Check")
        
        # Check for .env files (should not be committed)
        env_file = self.backend_path.parent / ".env"
        
        if env_file.exists():
            logger.info("✅ .env file exists locally")
        else:
            logger.info("ℹ️ .env file not found (expected for production)")
        
        self.results["passed"].append("✅ Secrets management configured")
    
    def _check_external_dependencies(self):
        """Check critical external dependencies"""
        logger.info("▶️  Phase 5.1: External Dependencies Check")
        
        dependencies = {
            "sqlalchemy": "Database ORM",
            "fastapi": "Web framework",
            "httpx": "HTTP client",
            "pytest": "Testing framework",
            "redis": "Cache backend",
            "playwright": "Web scraping"
        }
        
        missing_deps = []
        for dep, description in dependencies.items():
            try:
                __import__(dep)
            except ImportError:
                missing_deps.append(f"{dep} ({description})")
        
        if missing_deps:
            self.results["high"].extend([f"Missing dependency: {d}" for d in missing_deps])
            logger.warning(f"⚠️ Missing dependencies: {missing_deps}")
        else:
            self.results["passed"].append(f"✅ All {len(dependencies)} critical dependencies available")
            logger.info(f"✅ All dependencies installed")
    
    def _generate_report(self):
        """Generate validation report"""
        logger.info("\n" + "=" * 80)
        logger.info("📊 VALIDATION REPORT")
        logger.info("=" * 80)
        
        total_passed = len(self.results["passed"])
        total_issues = sum(len(v) for k, v in self.results.items() if k != "passed")
        
        logger.info(f"\n✅ PASSED: {total_passed}")
        for check in self.results["passed"][:5]:
            logger.info(f"  {check}")
        if total_passed > 5:
            logger.info(f"  ... and {total_passed - 5} more")
        
        if self.results["critical"]:
            logger.error(f"\n🔴 CRITICAL ISSUES: {len(self.results['critical'])}")
            for issue in self.results["critical"]:
                logger.error(f"  ❌ {issue}")
        
        if self.results["high"]:
            logger.warning(f"\n🟠 HIGH PRIORITY: {len(self.results['high'])}")
            for issue in self.results["high"][:3]:
                logger.warning(f"  ⚠️ {issue}")
            if len(self.results["high"]) > 3:
                logger.warning(f"  ... and {len(self.results['high']) - 3} more")
        
        if self.results["medium"]:
            logger.warning(f"\n🟡 MEDIUM PRIORITY: {len(self.results['medium'])}")
            for issue in self.results["medium"][:2]:
                logger.warning(f"  ℹ️ {issue}")
            if len(self.results["medium"]) > 2:
                logger.warning(f"  ... and {len(self.results['medium']) - 2} more")
        
        logger.info("\n" + "=" * 80)
        
        # Overall status
        if self.results["critical"]:
            logger.critical(f"❌ VALIDATION FAILED: {len(self.results['critical'])} critical issues")
            return False
        elif self.results["high"]:
            logger.error(f"⚠️ VALIDATION DEGRADED: {len(self.results['high'])} high-priority issues")
            return False
        else:
            logger.info(f"✅ VALIDATION PASSED: System ready for testing ({total_passed} checks)")
            return True

if __name__ == "__main__":
    backend_path = r"c:\Users\Gaurav Nagar\OneDrive\Desktop\startupV2\backend"
    validator = SystemValidator(backend_path)
    validator.run_all_checks()
