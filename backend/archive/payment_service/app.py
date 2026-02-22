from fastapi import FastAPI, Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
import httpx
import os
import uuid
from datetime import datetime
from pydantic import BaseModel
import logging

from database import get_db, Payment, Booking
from models import PaymentCreate, PaymentResponse, PaymentStatus

app = FastAPI(title="Payment Service", version="1.0.0")

security = HTTPBearer()
logger = logging.getLogger(__name__)

# Mock payment gateway (in production, integrate with real gateways like Stripe, Razorpay, etc.)
PAYMENT_GATEWAY_URL = os.getenv("PAYMENT_GATEWAY_URL", "https://api.mock-payment-gateway.com")

class PaymentGatewayRequest(BaseModel):
    amount: float
    currency: str = "INR"
    description: str
    customer_email: str
    booking_id: str

class PaymentGatewayResponse(BaseModel):
    transaction_id: str
    status: str
    gateway_response: dict

async def verify_token(credentials: HTTPAuthorizationCredentials = Depends(security), db: Session = Depends(get_db)):
    """Verify JWT token and return user info"""
    token = credentials.credentials
    # In production, validate JWT token with user service
    # For now, mock validation
    try:
        # Call user service to validate token
        async with httpx.AsyncClient() as client:
            response = await client.post(
                "http://user_service:8004/verify-token",
                json={"token": token}
            )
            if response.status_code != 200:
                raise HTTPException(status_code=401, detail="Invalid token")
            return response.json()
    except Exception:
        # Fallback for development
        return {"user_id": "mock_user", "username": "test"}

@app.post("/initiate", response_model=PaymentResponse)
async def initiate_payment(
    payment: PaymentCreate,
    current_user: dict = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Initiate a payment for a booking"""

    # Verify booking exists and belongs to user
    booking = db.query(Booking).filter(
        Booking.id == payment.booking_id,
        Booking.user_id == current_user["user_id"]
    ).first()

    if not booking:
        raise HTTPException(status_code=404, detail="Booking not found")

    # Check if payment already exists
    existing_payment = db.query(Payment).filter(
        Payment.booking_id == payment.booking_id
    ).first()

    if existing_payment:
        return existing_payment

    # Create payment record
    payment_id = str(uuid.uuid4())
    db_payment = Payment(
        id=payment_id,
        booking_id=payment.booking_id,
        amount=payment.amount,
        currency=payment.currency,
        status=PaymentStatus.PENDING,
        created_at=datetime.utcnow()
    )

    db.add(db_payment)
    db.commit()
    db.refresh(db_payment)

    # Call payment gateway
    try:
        gateway_request = PaymentGatewayRequest(
            amount=payment.amount,
            currency=payment.currency,
            description=f"Booking payment for {booking.route_info}",
            customer_email=current_user.get("email", "customer@example.com"),
            booking_id=payment.booking_id
        )

        # Mock payment gateway call
        # In production, call real payment gateway
        transaction_id = str(uuid.uuid4())

        # Update payment with transaction ID
        db_payment.transaction_id = transaction_id
        db_payment.gateway_response = {"mock": True, "transaction_id": transaction_id}
        db.commit()

        return db_payment

    except Exception as e:
        logger.error(f"Payment gateway error: {e}")
        db_payment.status = PaymentStatus.FAILED
        db.commit()
        raise HTTPException(status_code=500, detail="Payment processing failed")

@app.get("/status/{payment_id}", response_model=PaymentResponse)
async def get_payment_status(
    payment_id: str,
    current_user: dict = Depends(verify_token),
    db: Session = Depends(get_db)
):
    """Get payment status"""

    payment = db.query(Payment).filter(Payment.id == payment_id).first()
    if not payment:
        raise HTTPException(status_code=404, detail="Payment not found")

    # Verify ownership through booking
    booking = db.query(Booking).filter(
        Booking.id == payment.booking_id,
        Booking.user_id == current_user["user_id"]
    ).first()

    if not booking:
        raise HTTPException(status_code=403, detail="Access denied")

    return payment

@app.post("/webhook")
async def payment_webhook(webhook_data: dict):
    """Handle payment gateway webhooks"""

    # Verify webhook signature (in production)
    transaction_id = webhook_data.get("transaction_id")
    status = webhook_data.get("status")

    if not transaction_id or not status:
        raise HTTPException(status_code=400, detail="Invalid webhook data")

    # Update payment status
    # In production, implement proper webhook handling

    return {"status": "processed"}

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8005)