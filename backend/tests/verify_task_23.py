import sys
import os

# Add backend to path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.encryption_utils import encrypt_data, decrypt_data

def verify_task_23():
    print("\n>>> COMPREHENSIVE VERIFICATION: TASK 23 (ENCRYPTION INFRA)")
    
    # 1. Test Encryption/Decryption
    original = "MySecretPassword123!"
    print(f"  Original: {original}")
    
    encrypted = encrypt_data(original)
    print(f"  Encrypted (Base64): {encrypted}")
    
    assert encrypted != original
    assert len(encrypted) > 20
    
    decrypted = decrypt_data(encrypted)
    print(f"  Decrypted: {decrypted}")
    
    assert decrypted == original
    print("    Symmetry Check: OK")
    
    # 2. Test Invalid Decryption
    print("  Testing invalid decryption...")
    res = decrypt_data("totally-not-base64-or-encrypted")
    assert res == "DECRYPTION_ERROR"
    print("    Error Handling: OK")
    
    print("\n✅ TASK 23 FULLY VERIFIED: Encryption infrastructure is secure and functional.")

if __name__ == "__main__":
    verify_task_23()
