import sys
import os
from datetime import datetime

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from api.chat import _load_session, _save_session

def test_windowing():
    session_id = "test-window-session"
    
    # 1. Initialize session with entities
    session = _load_session(session_id)
    session["extracted_entities"] = {"source": "NDLS", "destination": "BCT"}
    
    # 2. Add 15 messages (Simulate conversation)
    for i in range(15):
        session["messages"].append({
            "role": "user",
            "content": f"Message {i+1}",
            "timestamp": datetime.utcnow().isoformat()
        })
    
    # 3. Save session (This should trigger windowing)
    _save_session(session_id, session)
    
    # 4. Reload and Verify
    reloaded = _load_session(session_id)
    
    msg_count = len(reloaded["messages"])
    has_entities = "source" in reloaded["extracted_entities"]
    
    print("--- Session Windowing Verification ---")
    print(f"Messages after 15 added: {msg_count} (Expected: 10)")
    print(f"Entities preserved: {has_entities} (Expected: True)")
    print(f"Entities: {reloaded['extracted_entities']}")
    
    if msg_count == 10 and has_entities:
        print("[PASS] Context windowing and entity persistence working.")
    else:
        print("[FAIL] Windowing logic error.")

if __name__ == "__main__":
    test_windowing()
