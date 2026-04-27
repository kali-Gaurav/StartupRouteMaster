import os
import hmac
import hashlib
import json
import requests
from dotenv import load_dotenv

# Load environment variables
load_dotenv('backend/.env')

KEY_ID = os.getenv("RAZORPAY_KEY_ID")
KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET")

print(f"Testing with KEY_ID: {KEY_ID}")

def test_create_order():
    url = "https://api.razorpay.com/v1/orders"
    payload = {
        "amount": 100, # 1 INR
        "currency": "INR",
        "receipt": "test_receipt_123"
    }
    response = requests.post(url, json=payload, auth=(KEY_ID, KEY_SECRET))
    print("Create Order Response:", response.status_code)
    if response.status_code == 200:
        print("Order Created Successfully:", response.json()['id'])
        return response.json()['id']
    else:
        print("Error:", response.text)
        return None

def test_verify_signature(order_id, payment_id, signature):
    message = f"{order_id}|{payment_id}"
    generated_signature = hmac.new(
        KEY_SECRET.encode(),
        message.encode(),
        hashlib.sha256
    ).hexdigest()
    
    if hmac.compare_digest(generated_signature, signature):
        print("Signature Verified Successfully")
        return True
    else:
        print("Signature Verification Failed")
        return False

if __name__ == "__main__":
    oid = test_create_order()
    # Mocking verify (since we can't get a real payment_id without browser)
    if oid:
        test_verify_signature(oid, "pay_mock123", "mock_sig")
