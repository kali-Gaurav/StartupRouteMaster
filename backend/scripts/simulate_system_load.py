import time
import multiprocessing
import os
import sys
from sqlalchemy.orm import Session

# Add backend to path
sys.path.append(os.path.join(os.getcwd(), 'backend'))
from database.session import SessionLocal, engine

def cpu_load():
    print("🔥 Injecting CPU load...")
    x = 0
    while True:
        x += 1

def db_load():
    print("💾 Injecting DB Connection load...")
    connections = []
    try:
        for i in range(15): # Max out the pool
            conn = engine.connect()
            connections.append(conn)
            print(f"  Connection {i+1} established.")
            time.sleep(0.5)
        
        print("✅ Pool saturated. Holding for 10 seconds...")
        time.sleep(10)
    finally:
        for c in connections:
            c.close()
        print("🧹 DB Connections released.")

if __name__ == "__main__":
    print("🚀 STARTING SYSTEM LOAD VERIFICATION...")
    
    # Run DB load in a separate thread to not block
    import threading
    t = threading.Thread(target=db_load)
    t.start()
    
    # Run CPU load for a few seconds
    p = multiprocessing.Process(target=cpu_load)
    p.start()
    
    time.sleep(15)
    p.terminate()
    print("🛑 Load simulation finished. Check Admin Dashboard for ROSE color gauges.")
