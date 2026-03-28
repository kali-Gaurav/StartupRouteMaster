import logging
from sqlalchemy import text
from typing import List, Optional
from database.session import SessionTransit

logger = logging.getLogger("hub_utils")

def get_top_centrality_hubs(limit: int = 50, db_session: Optional[SessionTransit] = None) -> List[str]:
    """
    [Task 121 Alignment] Schema corrected for Stations table.
    """
    if db_session:
        db = db_session
    else:
        db = SessionTransit()
        
    try:
        # [Task 121 Alignment] Use connectivity_score for REAL Hub Selection
        query = "SELECT id FROM stops WHERE connectivity_score > 0 ORDER BY connectivity_score DESC LIMIT :limit"
        rows = db.execute(text(query), {"limit": limit}).fetchall()
        codes = [int(r[0]) for r in rows]
        if codes:
            logger.info(f"Loaded {len(codes)} elite hubs (Sorted by Connectivity Score).")
            return codes
    except Exception as e:
        logger.warning(f"Failed to load dynamic hubs from DB: {e}")
    finally:
        if not db_session: db.close()

    # Safe Fallback (Legacy Top Hubs)
    return [
        'SDAH', 'KYN', 'HWH', 'MSB', 'DDU', 'BZA', 'TBM', 'ET', 'MS', 'CNB', 
        'BRC', 'BSL', 'MSF', 'DDJ', 'ST', 'MBM', 'BNXR', 'GDY', 'PNBE', 'MPK', 
        'CMP', 'STM', 'BWN', 'TLM', 'MKK', 'MN', 'MSC', 'NBK', 'PV', 'PZA', 
        'SP', 'TBMS', 'PER', 'VGLJ', 'BDC', 'NDLS', 'PRYJ', 'GZB', 'NGP', 'LKO'
    ]
