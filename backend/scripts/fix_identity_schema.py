import os
import psycopg2
from dotenv import load_dotenv
from pathlib import Path

def fix_schema():
    # Load .env
    root_dir = Path(__file__).resolve().parent.parent
    load_dotenv(dotenv_path=root_dir / '.env', override=True)
    
    url = os.getenv("DATABASE_URL")
    if not url:
        print("[FAIL] DATABASE_URL not found in .env")
        return

    print("Connecting to database...")
    try:
        conn = psycopg2.connect(url)
        conn.autocommit = True
        cursor = conn.cursor()
        
        # 1. Check if table exists
        cursor.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'identity_fingerprints');")
        exists = cursor.fetchone()[0]
        
        if not exists:
            print("[WARN] Table 'identity_fingerprints' does not exist. Creating it...")
            cursor.execute("""
                CREATE TABLE identity_fingerprints (
                    id VARCHAR(36) PRIMARY KEY,
                    user_id VARCHAR(36),
                    ip_address VARCHAR(45),
                    fingerprint_hash VARCHAR(128),
                    is_trusted BOOLEAN DEFAULT TRUE,
                    risk_score FLOAT DEFAULT 0.0,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
                CREATE INDEX ix_identity_fingerprints_ip_address ON identity_fingerprints (ip_address);
                CREATE INDEX ix_identity_fingerprints_fingerprint_hash ON identity_fingerprints (fingerprint_hash);
            """)
            print("[OK] Table created successfully.")
        else:
            print("[OK] Table 'identity_fingerprints' exists. Checking columns...")
            # 2. Check if created_at exists
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='identity_fingerprints' AND column_name='created_at';
            """)
            col_exists = cursor.fetchone()
            
            if not col_exists:
                print("[WARN] Column 'created_at' is missing. Adding it...")
                cursor.execute("ALTER TABLE identity_fingerprints ADD COLUMN created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP;")
                print("[OK] Column 'created_at' added.")
            else:
                print("[OK] Column 'created_at' already exists.")

            # 3. Check if user_agent exists
            cursor.execute("""
                SELECT column_name 
                FROM information_schema.columns 
                WHERE table_name='identity_fingerprints' AND column_name='user_agent';
            """)
            ua_exists = cursor.fetchone()
            
            if not ua_exists:
                print("[WARN] Column 'user_agent' is missing. Adding it...")
                cursor.execute("ALTER TABLE identity_fingerprints ADD COLUMN user_agent TEXT;")
                print("[OK] Column 'user_agent' added.")
            else:
                print("[OK] Column 'user_agent' already exists.")

        conn.close()
        print("[SUCCESS] Schema fix complete.")
        
    except Exception as e:
        print(f"[ERROR] Error fixing schema: {e}")

if __name__ == "__main__":
    fix_schema()
