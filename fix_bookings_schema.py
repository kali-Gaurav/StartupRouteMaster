import sqlite3
import os

def fix_schema():
    db_path = "backend/database/user_store.db"
    if not os.path.exists(db_path):
        print(f"❌ Database not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    columns_to_add = [
        ("escrow_status", "VARCHAR(20)"),
        ("escrow_message", "VARCHAR(255)"),
        ("upi_tx_id", "VARCHAR(100)"),
        ("utr_number", "VARCHAR(12)"),
        ("transaction_history", "JSON"),
        ("train_number", "VARCHAR(20)"),
        ("berth_preference", "VARCHAR(20)"),
        ("created_at", "DATETIME"),
        ("is_tatkal", "BOOLEAN"),
        ("priority", "INTEGER"),
        ("service_type", "VARCHAR(20)"),
        ("is_unlocked", "BOOLEAN"),
        ("agent_id", "VARCHAR(36)")
    ]
    
    for col_name, col_type in columns_to_add:
        try:
            print(f"Attempting to add column: {col_name}")
            cursor.execute(f"ALTER TABLE bookings ADD COLUMN {col_name} {col_type}")
            print(f"✅ Added {col_name}")
        except sqlite3.OperationalError as e:
            if "duplicate column name" in str(e):
                print(f"ℹ️ Column {col_name} already exists.")
            else:
                print(f"❌ Error adding {col_name}: {e}")
                
    conn.commit()
    conn.close()
    print("🚀 Schema fix completed.")

if __name__ == "__main__":
    fix_schema()
