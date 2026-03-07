import sqlite3
import os

def migrate_local_db():
    db_path = os.path.join("backend", "database", "user_store.db")
    if not os.path.exists(db_path):
        print(f"❌ DB not found at {db_path}")
        return

    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # 1. Add columns to bookings
    columns_to_add = [
        ("merchant_vpa", "TEXT"),
        ("service_type", "TEXT DEFAULT 'UNLOCK'"),
        ("ticket_pdf_url", "TEXT"),
        ("is_tatkal", "BOOLEAN DEFAULT 0"),
        ("priority", "INTEGER DEFAULT 0"),
        ("agent_id", "TEXT"),
        ("route_id", "TEXT"),
        ("trip_id", "TEXT"),
        ("berth_preference", "TEXT"),
        ("booking_details", "JSON")
    ]
    
    for col_name, col_type in columns_to_add:
        try:
            cursor.execute(f"ALTER TABLE bookings ADD COLUMN {col_name} {col_type}")
            print(f"✅ Added {col_name} to bookings")
        except sqlite3.OperationalError:
            print(f"ℹ️ Column {col_name} already exists in bookings")

    # 2. Add columns to users
    user_cols = [
        ("last_active_at", "DATETIME"),
        ("acquisition_source", "TEXT")
    ]
    for col_name, col_type in user_cols:
        try:
            cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_type}")
            print(f"✅ Added {col_name} to users")
        except sqlite3.OperationalError:
            print(f"ℹ️ Column {col_name} already exists in users")

    # 3. Create new tables if missing
    try:
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS merchant_vpas (
                id INTEGER PRIMARY KEY,
                vpa TEXT UNIQUE NOT NULL,
                name TEXT,
                daily_limit FLOAT,
                current_daily_volume FLOAT,
                is_active BOOLEAN,
                last_reset_at DATETIME
            )
        ''')
        print("✅ Table merchant_vpas verified/created")
        
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS merchant_vpa_snapshots (
                id INTEGER PRIMARY KEY,
                vpa TEXT,
                volume FLOAT,
                timestamp DATETIME
            )
        ''')
        print("✅ Table merchant_vpa_snapshots verified/created")

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS admin_dashboard_sessions (
                id TEXT PRIMARY KEY,
                admin_username TEXT,
                ip_address TEXT,
                user_agent TEXT,
                login_at DATETIME,
                expires_at DATETIME,
                is_active BOOLEAN
            )
        ''')
        print("✅ Table admin_dashboard_sessions verified/created")

        cursor.execute('''
            CREATE TABLE IF NOT EXISTS user_sessions (
                id TEXT PRIMARY KEY,
                user_id TEXT,
                started_at DATETIME,
                last_ping_at DATETIME,
                duration_seconds INTEGER,
                device_info TEXT,
                is_active BOOLEAN
            )
        ''')
        print("✅ Table user_sessions verified/created")

    except Exception as e:
        print(f"❌ Error creating tables: {e}")

    conn.commit()
    conn.close()
    print("🚀 Migration complete.")

if __name__ == "__main__":
    migrate_local_db()
