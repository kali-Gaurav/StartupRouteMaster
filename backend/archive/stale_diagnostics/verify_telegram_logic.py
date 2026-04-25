import secrets
from datetime import datetime, timedelta

def verify_linking_logic(token_input, stored_token, expiry):
    print(f"Verifying: Input='{token_input}', Stored='{stored_token}', Expiry={expiry}")
    if token_input.upper() == stored_token and datetime.utcnow() < expiry:
        return "✅ LINK SUCCESS"
    return "❌ LINK FAIL"

if __name__ == "__main__":
    # Simulate Task 3.1
    token = secrets.token_hex(4).upper()
    expiry = datetime.utcnow() + timedelta(minutes=10)
    
    print("--- Telegram Linking Logic Verification ---")
    print(verify_linking_logic(token, token, expiry))
    print(verify_linking_logic("WRONG123", token, expiry))
    print(verify_linking_logic(token, token, datetime.utcnow() - timedelta(seconds=1)))
