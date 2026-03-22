import logging
from sqlalchemy import text
from typing import List
from database.session import SessionTransit

logger = logging.getLogger("hub_utils")

def get_top_centrality_hubs(limit: int = 50) -> List[str]:
    """
    [Task 11.1] Fetch Top N stations by centrality score from database.
    Falls back to a safe default list if table is empty.
    """
    query = "SELECT code FROM stops WHERE centrality_score IS NOT NULL ORDER BY centrality_score DESC LIMIT :limit"
    db = SessionTransit()
    try:
        rows = db.execute(text(query), {"limit": limit}).fetchall()
        codes = [r[0] for r in rows]
        if codes:
            logger.info(f"Loaded {len(codes)} dynamic hubs by centrality.")
            return codes
    except Exception as e:
        logger.warning(f"Failed to load dynamic hubs: {e}")
    finally:
        db.close()

    # Safe Fallback (Legacy Top Hubs)
    return [
        'SDAH', 'KYN', 'HWH', 'MSB', 'DDU', 'BZA', 'TBM', 'ET', 'MS', 'CNB', 
        'BRC', 'BSL', 'MSF', 'DDJ', 'ST', 'MBM', 'BNXR', 'GDY', 'PNBE', 'MPK', 
        'CMP', 'STM', 'BWN', 'TLM', 'MKK', 'MN', 'MSC', 'NBK', 'PV', 'PZA', 
        'SP', 'TBMS', 'PER', 'VGLJ', 'BDC', 'NDLS', 'PRYJ', 'GZB', 'NGP', 'LKO'
    ]
