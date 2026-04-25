import os
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()
db_url = os.getenv("DATABASE_URL")
if not db_url:
    print("DATABASE_URL not found")
    exit(1)

engine = create_engine(db_url)

sql_commands = [
    "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS escrow_status VARCHAR(50) DEFAULT 'CREATED';",
    "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS escrow_message VARCHAR(255);",
    "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS upi_tx_id VARCHAR(100) UNIQUE;",
    "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS upi_utr_hash VARCHAR(64) UNIQUE;",
    "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS utr_number VARCHAR(12) UNIQUE;",
    "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS merchant_vpa VARCHAR(100);",
    "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS transaction_history JSONB DEFAULT '[]'::jsonb;",
    "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS is_tatkal BOOLEAN DEFAULT FALSE;",
    "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS priority INTEGER DEFAULT 10;",
    "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS service_type VARCHAR(20) DEFAULT 'UNLOCK';",
    "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS is_unlocked BOOLEAN DEFAULT FALSE;",
    "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS agent_id VARCHAR(36);",
    "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS train_number VARCHAR(20);",
    "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS berth_preference VARCHAR(20);",
    "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS fingerprint_id VARCHAR(36);",
    "ALTER TABLE bookings ADD COLUMN IF NOT EXISTS ticket_pdf_url VARCHAR(1024);",
]

with engine.connect() as conn:
    print("Executing surgical schema repair on 'bookings'...")
    for cmd in sql_commands:
        try:
            conn.execute(text(cmd))
            conn.commit()
            print(f"OK: {cmd[:40]}...")
        except Exception as e:
            print(f"ERR: {cmd[:40]}... -> {e}")
            conn.rollback()

print("Schema repair complete.")
