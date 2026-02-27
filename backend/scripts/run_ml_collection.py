#!/usr/bin/env python3
"""
Run ML Pipeline in Data Collection Mode
========================================

This script runs the ML training pipeline in data collection mode only.
Use this during the first 30 days of staging to validate data quality.

Usage:
    # Data collection mode (default)
    python run_ml_data_collection.py

    # Force data collection mode explicitly
    ML_DATA_COLLECTION_ONLY=true python run_ml_data_collection.py

    # Training mode (after 30 days of data)
    ML_DATA_COLLECTION_ONLY=false python run_ml_data_collection.py
"""

import os
import sys
import subprocess
import logging

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Run ML pipeline with appropriate environment variables"""

    # Set data collection mode by default
    data_collection_mode = os.getenv('ML_DATA_COLLECTION_ONLY', 'true').lower() == 'true'

    # Database configuration
    db_url = os.getenv('DATABASE_URL', 'postgresql://routemaster:routemaster@localhost/routemaster_ml')
    redis_url = os.getenv('REDIS_URL', 'redis://localhost:6379')

    logger.info("🚀 Starting RouteMaster ML Pipeline")
    logger.info(f"Data Collection Mode: {data_collection_mode}")
    logger.info(f"Database: {db_url.replace(db_url.split('@')[0].split('//')[1].split(':')[0], '***')}")

    if data_collection_mode:
        logger.info("📊 Running in DATA COLLECTION MODE")
        logger.info("   - Feature extraction and storage")
        logger.info("   - Data quality monitoring")
        logger.info("   - No model training")
        logger.info("   - Safe for production staging")
    else:
        logger.warning("🤖 Running in TRAINING MODE")
        logger.warning("   - Will train production models")
        logger.warning("   - Ensure you have 30+ days of quality data")
        logger.warning("   - Models will be registered for deployment")

    # Set environment variables
    env = os.environ.copy()
    env['DATABASE_URL'] = db_url
    env['REDIS_URL'] = redis_url
    env['ML_DATA_COLLECTION_ONLY'] = str(data_collection_mode).lower()

    # Run the pipeline
    try:
        cmd = [sys.executable, 'ml_training_pipeline.py']
        logger.info(f"Executing: {' '.join(cmd)}")

        result = subprocess.run(
            cmd,
            cwd=os.path.dirname(__file__),
            env=env,
            capture_output=True,
            text=True,
            timeout=3600  # 1 hour timeout
        )

        # Log output
        if result.stdout:
            logger.info("Pipeline Output:")
            for line in result.stdout.strip().split('\n'):
                logger.info(f"  {line}")

        if result.stderr:
            logger.warning("Pipeline Warnings/Errors:")
            for line in result.stderr.strip().split('\n'):
                logger.warning(f"  {line}")

        if result.returncode == 0:
            logger.info("✅ ML Pipeline completed successfully!")
            if data_collection_mode:
                logger.info("💡 Data collection complete. Check Grafana for quality metrics.")
        else:
            logger.error(f"❌ ML Pipeline failed with exit code: {result.returncode}")
            sys.exit(result.returncode)

    except subprocess.TimeoutExpired:
        logger.error("❌ ML Pipeline timed out after 1 hour")
        sys.exit(1)
    except KeyboardInterrupt:
        logger.info("🛑 ML Pipeline interrupted by user")
        sys.exit(1)
    except Exception as e:
        logger.error(f"❌ Unexpected error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
