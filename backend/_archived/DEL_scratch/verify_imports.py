import sys
import os
import importlib
import logging

# Add backend to path
sys.path.append(os.path.abspath('.'))

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("verify_imports")

# Test major entry points
MODULES_TO_TEST = [
    "api.communication.bot_api",
    "services.intelligence.bot_handler",
    "services.telegram.handler",
    "services.planning.multimodal",
    "database.models.core"
]

def verify():
    failed = []
    for module_name in MODULES_TO_TEST:
        try:
            logger.info(f"Checking {module_name}...")
            importlib.import_module(module_name)
            logger.info(f"✓ {module_name} imported successfully")
        except Exception as e:
            logger.error(f"✗ Failed to import {module_name}: {e}")
            import traceback
            traceback.print_exc()
            failed.append(module_name)
    
    if failed:
        logger.error(f"Verification FAILED for: {', '.join(failed)}")
        sys.exit(1)
    else:
        logger.info("Verification PASSED")

if __name__ == "__main__":
    verify()
