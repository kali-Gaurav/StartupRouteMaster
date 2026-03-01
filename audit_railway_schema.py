import os
import sys
from sqlalchemy import text

# Add backend to path
sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))

from database.session import engine_write

def audit_production_schema():
    print("=== AUDITING RAILWAY PRODUCTION SCHEMA ===")
    conn = engine_write.connect()
    
    # 1. Check/Create Table: train_availability_cache
    res = conn.execute(text("SELECT 1 FROM information_schema.tables WHERE table_name='train_availability_cache'")).fetchone()
    if not res:
        print("[MISSING] train_availability_cache table. Creating...")
        conn.execute(text("""
            CREATE TABLE train_availability_cache (
                id VARCHAR(36) PRIMARY KEY,
                train_number VARCHAR(20) NOT NULL,
                from_station_code VARCHAR(10) NOT NULL,
                to_station_code VARCHAR(10) NOT NULL,
                journey_date DATE NOT NULL,
                class_type VARCHAR(10) NOT NULL,
                quota VARCHAR(10) NOT NULL,
                status_text VARCHAR(100),
                seats_available INTEGER,
                fare INTEGER,
                last_updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uq_train_availability UNIQUE (train_number, from_station_code, to_station_code, journey_date, class_type, quota)
            )
        """))
        conn.commit()
        print("  -> Success: Created train_availability_cache")
    else:
        print("[OK] train_availability_cache exists")

    # 2. Check other columns
    checks = [
        ("users", "supabase_id"),
        ("unlocked_routes", "cached_route_id"),
        ("payment_sessions", "verification_details"),
        ("booking_requests", "verification_status"),
        ("booking_requests", "route_id")
    ]
    
    for table, col in checks:
        query = text(f"""
            SELECT column_name 
            FROM information_schema.columns 
            WHERE table_name='{table}' AND column_name='{col}'
        """)
        res = conn.execute(query).fetchone()
        exists = res is not None
        print(f"[{'OK' if exists else 'MISSING'}] {table}.{col}")
        
        if not exists:
            print(f"  -> Fixing: Adding {col} to {table}...")
            col_type = "VARCHAR(255)"
            if col == "verification_details": col_type = "JSONB"
            if col == "route_id": col_type = "VARCHAR(36)"
            
            try:
                conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
                conn.commit()
                print(f"  -> Success: Added {col} to {table}")
            except Exception as e:
                print(f"  -> Failed to add {col}: {e}")
    
    conn.close()
    print("=== AUDIT COMPLETE ===")

if __name__ == "__main__":
    audit_production_schema()
