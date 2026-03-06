import sys
import os
import io

# Add backend to path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from utils.payments import generate_upi_uri, generate_upi_qr, create_short_payment_url
from services.cache_service import cache_service

def verify_task_1():
    print("=== Verifying Task 1: Advanced NPCI UPI Generator ===")
    
    # 1. Generate URI 2.0
    merchant_vpa = "routemaster@bank"
    merchant_name = "RouteMaster"
    amount = 39.0
    min_amount = 10.0
    
    uri, tid = generate_upi_uri(
        merchant_vpa=merchant_vpa,
        merchant_name=merchant_name,
        amount=amount,
        min_amount=min_amount,
        transaction_note="Test Payment"
    )
    
    print(f"Generated URI: {uri}")
    assert "upi://pay?" in uri
    assert "pa=routemaster%40bank" in uri
    assert "am=39.00" in uri
    assert "mam=10.00" in uri
    assert "mc=4112" in uri
    print("[OK] URI 2.0 Generation")

    # 2. Generate QR Code
    qr_io = generate_upi_qr(uri)
    assert isinstance(qr_io, io.BytesIO)
    assert qr_io.getbuffer().nbytes > 0
    print("[OK] QR Code Generation")

    # 3. Create Short URL
    # Ensure cache_service is available for this test
    if not cache_service.is_available():
        print("[SKIP] Short URL (Redis not available)")
    else:
        short_url = create_short_payment_url(uri)
        print(f"Short URL: {short_url}")
        assert "http://localhost:8000/api/payment/u/" in short_url
        
        # Verify it's in Redis
        short_id = short_url.split("/")[-1]
        stored_uri = cache_service.get(f"upi_short:{short_id}")
        assert stored_uri == uri
        print("[OK] Short URL Generation & Redis Storage")

    print("=== Task 1 Verification Complete ===")

if __name__ == "__main__":
    verify_task_1()
