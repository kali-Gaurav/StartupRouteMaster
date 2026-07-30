import asyncio
import sys
import os
import base64

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.encryption_utils import encrypt_data_hardened, decrypt_data_hardened

async def verify_task_33():
    print("\n>>> STARTING VERIFICATION: MVP TASK 33 (AES-GCM HARDENING)")
    
    original = "MySecretIRCTC_123!"
    print(f"  Original Secret: {original}")

    # 1. Test Encryption
    print("  Encrypting with AES-GCM...")
    ct_b64, iv_b64 = encrypt_data_hardened(original)
    
    print(f"    Ciphertext (Base64): {ct_b64[:20]}...")
    print(f"    IV (Base64): {iv_b64}")
    
    assert ct_b64 != original
    assert len(base64.b64decode(iv_b64)) == 12 # GCM IV standard
    print("    ✅ SUCCESS: Encrypted with 12-byte unique IV.")

    # 2. Test Decryption
    print("\n  Decrypting...")
    recovered = decrypt_data_hardened(ct_b64, iv_b64)
    print(f"    Recovered: {recovered}")
    assert recovered == original
    print("    ✅ SUCCESS: Decryption recovered original perfectly.")

    # 3. Test Authentication Integrity (Subtask 33.3)
    print("\n[33.3] Testing Data Integrity (Tamper Detection)...")
    # Change one byte in ciphertext
    ct_bytes = list(base64.b64decode(ct_b64))
    ct_bytes[0] ^= 0xFF # Flip bits
    ct_tampered = base64.b64encode(bytes(ct_bytes)).decode()
    
    tampered_res = decrypt_data_hardened(ct_tampered, iv_b64)
    print(f"    Result after tampering: {tampered_res}")
    assert tampered_res == "DECRYPTION_ERROR"
    print("    ✅ SUCCESS: AES-GCM caught tampered data (Auth Tag check).")

    # 4. Test Multi-use uniqueness
    _, iv2 = encrypt_data_hardened(original)
    assert iv_b64 != iv2
    print("    ✅ SUCCESS: Consecutive encryptions use unique IVs.")

    print("\n✅ ALL MVP TASK 33 SUBTASKS VERIFIED!")

if __name__ == "__main__":
    asyncio.run(verify_task_33())
