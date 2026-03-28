import sqlite3
import os
import logging

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("fix_tables")

def fix_sagas():
    db_path = "nexus_sagas.db"
    logger.info(f"Checking {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS sagas (
            tx_id TEXT PRIMARY KEY,
            status TEXT,
            metadata TEXT,
            created_at TEXT,
            updated_at TEXT
        )
    """)
    conn.commit()
    conn.close()
    logger.info(f"Table 'sagas' ensured in {db_path}")

def fix_reliability_scores():
    db_path = os.path.join("database", "transit_graph.db")
    logger.info(f"Checking {db_path}...")
    if not os.path.exists(db_path):
        logger.warning(f"{db_path} does not exist. Skipping.")
        return
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS reliability_scores (
            from_stop_id INTEGER,
            to_stop_id INTEGER,
            score REAL,
            PRIMARY KEY (from_stop_id, to_stop_id)
        )
    """)
    conn.commit()
    conn.close()
    logger.info(f"Table 'reliability_scores' ensured in {db_path}")

if __name__ == "__main__":
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    os.chdir("..") # Go to backend root
    fix_sagas()
    fix_reliability_scores()
