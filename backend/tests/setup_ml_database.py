#!/usr/bin/env python3
"""
ML Feature Store Database Setup
===============================

This script sets up the ML feature store database with proper schema and indexes.
Run this before starting the ML training pipeline.
"""

import os
import sys
import logging
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def get_database_url():
    """Get database URL from environment or use default"""
    return os.getenv('DATABASE_URL', 'postgresql://routemaster:routemaster@localhost/routemaster_ml')

def run_migration(db_url: str, schema_file: str):
    """Run database migration from SQL file"""

    logger.info(f"Connecting to database: {db_url.replace(db_url.split('@')[0].split('//')[1].split(':')[0], '***')}")

    try:
        engine = create_engine(db_url)

        # Test connection
        with engine.connect() as conn:
            result = conn.execute(text("SELECT version()"))
            version = result.fetchone()[0]
            logger.info(f"Connected to PostgreSQL: {version}")

        # Read and execute schema
        logger.info(f"Reading schema from: {schema_file}")
        with open(schema_file, 'r') as f:
            schema_sql = f.read()

        # Split into individual statements
        statements = [stmt.strip() for stmt in schema_sql.split(';') if stmt.strip()]

        with engine.connect() as conn:
            for i, statement in enumerate(statements, 1):
                if statement:
                    logger.info(f"Executing statement {i}/{len(statements)}")
                    try:
                        conn.execute(text(statement))
                        conn.commit()
                    except SQLAlchemyError as e:
                        logger.error(f"Failed to execute statement {i}: {e}")
                        # Continue with other statements
                        continue

        logger.info("Migration completed successfully!")

        # Verify tables were created
        with engine.connect() as conn:
            result = conn.execute(text("""
                SELECT table_name
                FROM information_schema.tables
                WHERE table_schema = 'public'
                AND table_name IN ('route_search_events', 'route_features', 'training_datasets', 'model_metadata')
                ORDER BY table_name;
            """))

            tables = [row[0] for row in result.fetchall()]
            logger.info(f"Created tables: {', '.join(tables)}")

            if len(tables) == 4:
                logger.info("✅ All ML feature store tables created successfully!")
            else:
                logger.warning(f"⚠️  Expected 4 tables, found {len(tables)}")

    except SQLAlchemyError as e:
        logger.error(f"Database migration failed: {e}")
        sys.exit(1)
    except FileNotFoundError:
        logger.error(f"Schema file not found: {schema_file}")
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        sys.exit(1)

def main():
    """Main setup function"""

    # Database configuration
    db_url = get_database_url()
    schema_file = 'ml_feature_store_schema.sql'

    logger.info("RouteMaster ML Feature Store Setup")
    logger.info("=" * 40)

    # Check if schema file exists
    if not os.path.exists(schema_file):
        logger.error(f"Schema file not found: {schema_file}")
        logger.info("Make sure you're running this from the backend directory")
        sys.exit(1)

    # Run migration
    run_migration(db_url, schema_file)

    # Print next steps
    logger.info("\nNext Steps:")
    logger.info("1. Start the ML training pipeline:")
    logger.info("   python ml_training_pipeline.py")
    logger.info("2. Monitor pipeline metrics in Grafana")
    logger.info("3. Check dataset quality with:")
    logger.info("   psql -d routemaster_ml -c 'SELECT * FROM dataset_quality;'")

if __name__ == "__main__":
    main()
