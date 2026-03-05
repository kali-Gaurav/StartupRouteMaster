import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from database.session import SessionLocal
from sqlalchemy import text

def fix_bookings():
    db = SessionLocal()
    engine = db.get_bind()
    conn = engine.connect()
    
    columns_to_add = [
        "escrow_status TEXT DEFAULT 'CREATED'",
        "upi_tx_id TEXT",
        "utr_number TEXT",
        "train_number TEXT",
        "berth_preference TEXT",
        "created_at DATETIME"
    ]
    
    for col in columns_to_add:
        try:
            conn.execute(text(f"ALTER TABLE bookings ADD COLUMN {col}"))
            conn.commit()
            print(f"✅ Added column: {col}")
        except Exception as e:
            if "duplicate column name" in str(e):
                print(f"ℹ️ Column already exists: {col.split()[0]}")
            else:
                print(f"❌ Failed to add {col}: {e}")
    
    conn.close()
    db.close()

if __name__ == "__main__":
    fix_bookings()
