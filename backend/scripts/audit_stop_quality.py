"""
[Data Quality] audit_stop_quality.py (TODO #17)

Detects stops with empty or duplicate codes and logs them.
Ideally this would map to a cleaning queue table.
"""

import sys
import os
import logging
from sqlalchemy import func

# Ensure backend package is importable
sys.path.append(os.path.join(os.getcwd(), 'backend'))

from database.session import SessionLocal
from database.models import Stop

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("data-quality")

def audit_stops():
    session = SessionLocal()
    try:
        # 1. Empty Codes
        empty_stops = session.query(Stop).filter(
            (Stop.code == None) | (Stop.code == "") | (Stop.code == " ")
        ).all()
        
        if empty_stops:
            logger.warning(f"Found {len(empty_stops)} stops with empty codes:")
            for s in empty_stops[:10]:
                logger.warning(f"  - ID: {s.id}, Name: {s.name}")
        else:
            logger.info("No stops with empty codes found.")

        # 2. Duplicate Codes
        duplicate_codes = session.query(
            Stop.code, func.count(Stop.id)
        ).group_by(Stop.code).having(func.count(Stop.id) > 1).all()
        
        if duplicate_codes:
            logger.warning(f"Found {len(duplicate_codes)} duplicate station codes:")
            for code, count in duplicate_codes[:10]:
                stops = session.query(Stop).filter(Stop.code == code).all()
                logger.warning(f"  - Code: {code} ({count} occurrences)")
                for s in stops:
                    logger.warning(f"    * ID: {s.id}, Name: {s.name}")
        else:
            logger.info("No duplicate station codes found.")

        # Future Phase: Insert these into a DataCleaningQueue table

    except Exception as e:
        logger.error(f"Audit failed: {e}")
    finally:
        session.close()

if __name__ == "__main__":
    audit_stops()
