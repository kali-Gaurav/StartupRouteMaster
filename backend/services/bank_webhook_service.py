import re
import logging
import json
import base64
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from database.models import BankTransaction, Booking, EscrowStatus
from services.cache_service import cache_service
from schemas.bank_webhook import BankSMSPayload
from config import Config

logger = logging.getLogger(__name__)

from services.ws_manager import ws_manager

class BankWebhookService:
    """
    Task 2 & 3: Real-Time Bank SMS/Webhook Integration.
    Handles SMS parsing, UTR deduplication, and transaction matching.
    """
    
    # Task 2.2: Regex engine for 20+ Indian banks
    PATTERNS = [
        r"SBI.*Debited.*INR\s*(?P<amount>[\d\.]+).*Ref\s*(?P<utr>\d{12})",
        r"HDFC.*Rs\s*(?P<amount>[\d\.]+).*Ref\s*(?P<utr>\d{12})",
        r"ICICI.*Rs\s*(?P<amount>[\d\.]+).*Ref\s*(?P<utr>\d{12})",
        r"AXIS.*INR\s*(?P<amount>[\d\.]+).*UTR\s*(?P<utr>\d{12})",
        r"KOTAK.*Rs\.\s*(?P<amount>[\d\.]+).*Ref\.\s*(?P<utr>\d{12})",
        r"PNB.*Rs\.\s*(?P<amount>[\d\.]+).*Ref\s*(?P<utr>\d{12})",
        r"BOB.*INR\s*(?P<amount>[\d\.]+).*UTR\s*(?P<utr>\d{12})",
        r"UNION.*Rs\.\s*(?P<amount>[\d\.]+).*UTR\s*(?P<utr>\d{12})",
        r"CANARA.*INR\s*(?P<amount>[\d\.]+).*UTR\s*(?P<utr>\d{12})",
        r"INDUSIND.*Rs\s*(?P<amount>[\d\.]+).*Ref\s*(?P<utr>\d{12})",
        r"YES.*INR\s*(?P<amount>[\d\.]+).*Ref\s*(?P<utr>\d{12})",
        r"IDFC.*Rs\s*(?P<amount>[\d\.]+).*UTR\s*(?P<utr>\d{12})",
        r"FEDERAL.*INR\s*(?P<amount>[\d\.]+).*Ref\s*(?P<utr>\d{12})",
        r"SOUTH\s*INDIAN.*Rs\s*(?P<amount>[\d\.]+).*UTR\s*(?P<utr>\d{12})",
        r"KARNATAKA.*INR\s*(?P<amount>[\d\.]+).*Ref\s*(?P<utr>\d{12})",
        r"MAHARASHTRA.*Rs\s*(?P<amount>[\d\.]+).*UTR\s*(?P<utr>\d{12})",
        r"INDIAN\s*BANK.*INR\s*(?P<amount>[\d\.]+).*Ref\s*(?P<utr>\d{12})",
        r"CENTRAL\s*BANK.*Rs\s*(?P<amount>[\d\.]+).*UTR\s*(?P<utr>\d{12})",
        r"UCO.*INR\s*(?P<amount>[\d\.]+).*UTR\s*(?P<utr>\d{12})",
        r"PAYTM.*Rs\.\s*(?P<amount>[\d\.]+).*Ref\s*(?P<utr>\d{12})",
        r"(Paid|Sent|Transfer).*?(?P<amount>[\d\.]+).*?(UTR|Ref).*?(?P<utr>\d{12})",
        r"credited.*?(?P<amount>[\d\.]+).*?UTR.*?(?P<utr>\d{12})",
        # Generic fallback for any bank SMS containing a 12-digit number and decimal amount
        r"(?P<amount>\d+\.\d{2}).*?(?P<utr>\d{12})",
        r"(?P<utr>\d{12}).*?(?P<amount>\d+\.\d{2})",
        # Task 4: Match RM_ tag (Short ID)
        r"RM_(?P<short_id>[A-Z0-9]{8})"
    ]

    def decrypt_payload(self, ciphertext_b64: str, iv_b64: str) -> str:
        """Task 2.7: End-to-end encryption for SMS data payload using AES-256-CBC."""
        try:
            # Task 2.7: Uses secure secret from config
            secret = Config.BANK_WEBHOOK_SECRET or Config.RAZORPAY_KEY_SECRET
            if not secret:
                raise ValueError("No encryption secret found in config")
                
            key = secret[:32].encode('utf-8').ljust(32, b'\0') # 32 bytes for AES-256
            iv = base64.b64decode(iv_b64)
            ciphertext = base64.b64decode(ciphertext_b64)
            cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
            decryptor = cipher.decryptor()
            plaintext_padded = decryptor.update(ciphertext) + decryptor.finalize()
            # Simple PKCS7 unpad (assuming padded payload)
            padding_len = plaintext_padded[-1]
            plaintext = plaintext_padded[:-padding_len].decode('utf-8')
            return plaintext
        except Exception as e:
            logger.error(f"Failed to decrypt SMS payload: {e}")
            raise ValueError("Decryption failed")

    def parse_sms(self, body: str) -> Tuple[Optional[float], Optional[str]]:
        """Extracts amount and UTR from SMS body using regex."""
        for pattern in self.PATTERNS:
            match = re.search(pattern, body, re.IGNORECASE | re.DOTALL)
            if match:
                try:
                    amount_str = match.group("amount")
                    utr = match.group("utr")
                    return float(amount_str), utr
                except (ValueError, IndexError):
                    continue
        return None, None

    async def process_transaction(self, db: Session, payload: BankSMSPayload) -> Dict[str, Any]:
        """
        Main logic for Task 2 & 3.
        - Parsers SMS
        - Filters duplicates via Redis
        - Matches with PENDING bookings (UTR first, then Cent-Matching)
        - Notifies via WebSockets
        """
        receive_time = datetime.utcnow()
        
        # Task 2.8: Battery/Connectivity monitoring
        if payload.status:
            logger.info(f"Companion App Status - Device: {payload.device_id}, Battery: {payload.status.battery_level}%")

        sms_body = payload.body
        if payload.is_encrypted:
            try:
                sms_body = self.decrypt_payload(payload.body, payload.iv)
            except Exception as e:
                return {"success": False, "message": "Failed to decrypt SMS payload"}

        amount, utr = self.parse_sms(sms_body)
        
        if not utr:
            logger.warning(f"Failed to parse UTR from SMS: {sms_body[:50]}...")
            return {"success": False, "message": "Could not parse UTR"}

        # 2.4 Duplicate UTR filtering
        dedup_key = f"utr_processed:{utr}"
        if cache_service.get(dedup_key):
            return {"success": False, "message": "Duplicate UTR", "utr": utr}
        cache_service.set(dedup_key, "1", ttl_seconds=86400)

        # Save to BankTransaction
        txn = BankTransaction(
            utr=utr,
            amount=amount or 0.0,
            bank_name=payload.sender,
            raw_payload=sms_body,
            sender_phone=payload.device_id,
            received_at=receive_time,
            sms_timestamp=payload.timestamp,
            status="PENDING"
        )
        db.add(txn)
        
        matched = False
        booking_id = None
        
        # 0. Attempt RM_ tag (Short ID) matching (Highest confidence)
        short_id_match = re.search(r"RM_(?P<sid>[A-Z0-9]{8})", sms_body)
        if short_id_match:
            sid = short_id_match.group("sid")
            # The booking ID in DB starts with this Short ID (from uuid hex or our logic)
            # In initiate_service we do: short_id = booking_id_placeholder[:8].upper()
            booking = db.query(Booking).filter(
                Booking.id.like(f"{sid.lower()}%"),
                Booking.escrow_status.in_([EscrowStatus.CREATED, EscrowStatus.UTR_SUBMITTED])
            ).first()
            if booking:
                logger.info(f"Short-ID matching success! SID {sid} matched Booking {booking.id}")
                booking.utr_number = utr # Save the UTR for future ref

        # 1. Attempt UTR Matching (User manual entry vs SMS)
        if not booking:
            booking = db.query(Booking).filter(
                Booking.utr_number == utr,
                Booking.escrow_status == EscrowStatus.UTR_SUBMITTED
            ).first()
        
        # 2. Attempt Cent-Matching Fallback (Amount-based identification)
        if not booking and amount:
            # Find a booking with this exact amount (including paisa offset) created recently
            booking = db.query(Booking).filter(
                Booking.amount_paid == amount,
                Booking.escrow_status == EscrowStatus.CREATED
            ).order_by(Booking.created_at.desc()).first()
            
            if booking:
                logger.info(f"Cent-matching success! Amount ₹{amount} matched Booking {booking.id}")
                booking.utr_number = utr # Save the UTR we just found

        if booking:
            # Promote status
            from database.models import EscrowStatus
            booking.escrow_status = EscrowStatus.VERIFIED
            booking.escrow_message = "✅ Payment verified automatically via bank SMS hook."
            txn.status = "MATCHED"
            matched = True
            booking_id = str(booking.id)
            
            # Record volume for VPA rotation limits
            from services.merchant_vpa_service import merchant_vpa_service
            if booking.merchant_vpa:
                merchant_vpa_service.record_volume(booking.merchant_vpa, booking.amount_paid)

            # Trigger real-time UI notification
            await ws_manager.broadcast_log(booking_id, "🔍 Payment detected in bank statement. Matching amount...")
            await asyncio.sleep(1)
            await ws_manager.broadcast_log(booking_id, "✅ Payment Secured! Funds held in RouteMaster Escrow.", "VERIFIED")
            
            # Log admin alert for AGENT_BOOKING
            if booking.service_type == "AGENT_BOOKING":
                logger.info(f"🚨 ADMIN ALERT: New AGENT_BOOKING ready for processing! ID: {booking_id}")
        
        db.commit()
        return {
            "success": True,
            "message": "Matched" if matched else "Saved but unmatched",
            "utr": utr,
            "matched": matched,
            "booking_id": booking_id
        }

    async def process_csv(self, db: Session, csv_content: str) -> Dict[str, Any]:
        """
        Task 2.10: Failover to manual bank CSV upload.
        Parses a standard bank CSV to reconcile missing UTRs.
        Expected columns loosely: Date, Description, Amount, Ref/UTR
        """
        import csv
        import io
        
        reader = csv.reader(io.StringIO(csv_content))
        total = 0
        matched_count = 0
        errors = []
        
        for row in reader:
            try:
                # Basic heuristic parsing
                row_str = " ".join(row)
                amount, utr = self.parse_sms(row_str)
                
                if not utr:
                    # Look for explicit 12-digit numbers
                    matches = re.findall(r"\b\d{12}\b", row_str)
                    if matches:
                        utr = matches[0]
                
                if not utr:
                    continue
                    
                total += 1
                
                # Mock a payload to reuse the existing process logic
                payload = BankSMSPayload(
                    sender="CSV_UPLOAD",
                    body=row_str,
                    timestamp=datetime.utcnow()
                )
                
                # To prevent overriding amounts from regex, we manually check DB here or pass amount
                # Since we just want to process it, we can call process_transaction directly
                # However, since process_transaction expects the amount to be parsed from the body,
                # the row_str needs to be somewhat formatted. The regex fallback works for most.
                
                result = await self.process_transaction(db, payload)
                if result.get("matched"):
                    matched_count += 1
                    
            except Exception as e:
                errors.append(str(e))
                
        return {
            "total": total,
            "matched": matched_count,
            "errors": errors[:5] # limit error output
        }

