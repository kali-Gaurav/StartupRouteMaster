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

class BankWebhookService:
    """
    Task 2: Real-Time Bank SMS/Webhook Integration.
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
        r"credited.*?(?P<amount>[\d\.]+).*?UTR.*?(?P<utr>\d{12})"
    ]

    def decrypt_payload(self, ciphertext_b64: str, iv_b64: str) -> str:
        """Task 2.7: End-to-end encryption for SMS data payload using AES-256-CBC."""
        try:
            key = Config.RAZORPAY_KEY_SECRET[:32].encode('utf-8').ljust(32, b'\0') # 32 bytes for AES-256
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
                    amount = float(match.group("amount"))
                    utr = match.group("utr")
                    return amount, utr
                except (ValueError, IndexError):
                    continue
        return None, None

    async def process_transaction(self, db: Session, payload: BankSMSPayload) -> Dict[str, Any]:
        """
        Main logic for Task 2.
        - Parsers SMS
        - Filters duplicates via Redis
        - Matches with PENDING bookings
        - Tracks latency
        """
        receive_time = datetime.utcnow()
        
        # Task 2.8: Battery/Connectivity monitoring
        if payload.status:
            logger.info(f"Companion App Status - Device: {payload.device_id}, "
                        f"Battery: {payload.status.battery_level}%, "
                        f"Charging: {payload.status.is_charging}, "
                        f"Net: {payload.status.network_type} ({payload.status.signal_strength}dBm)")
            if payload.status.battery_level < 15 and not payload.status.is_charging:
                logger.warning("Companion App battery is critically low!")

        sms_body = payload.body
        # Task 2.7: E2E Decryption
        if payload.is_encrypted:
            try:
                sms_body = self.decrypt_payload(payload.body, payload.iv)
            except Exception as e:
                return {"success": False, "message": "Failed to decrypt SMS payload"}

        amount, utr = self.parse_sms(sms_body)
        
        if not utr:
            logger.warning(f"Failed to parse UTR from SMS: {sms_body[:50]}...")
            return {"success": False, "message": "Could not parse UTR"}

        # 2.4 Duplicate UTR filtering at the webhook layer (using Redis)
        dedup_key = f"utr_processed:{utr}"
        if cache_service.get(dedup_key):
            logger.info(f"Duplicate UTR detected: {utr}")
            return {"success": False, "message": "Duplicate UTR", "utr": utr}
        
        # Mark as seen for 24 hours
        cache_service.set(dedup_key, "1", ttl_seconds=86400)

        # 2.6 Latency tracking (SMS Time vs Webhook Received Time)
        latency = (receive_time - payload.timestamp).total_seconds()
        logger.info(f"Transaction {utr} received with latency: {latency}s")

        # Save to BankTransaction for audit
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
        
        # 2.5 Amount matching logic (Tolerance ±0.01)
        booking = db.query(Booking).filter(Booking.utr_number == utr).first()
        
        matched = False
        booking_id = None
        
        if booking:
            # Check amount tolerance
            if abs(booking.amount_paid - amount) <= 0.01:
                booking.escrow_status = EscrowStatus.VERIFIED
                booking.booking_status = "confirmed" # Auto-promote
                txn.status = "MATCHED"
                matched = True
                booking_id = str(booking.id)
                logger.info(f"UTR {utr} matched with Booking {booking.id}")
            else:
                logger.warning(f"Amount mismatch for UTR {utr}: Expected {booking.amount_paid}, got {amount}")
                txn.status = "AMOUNT_MISMATCH"
        
        db.commit()
        
        return {
            "success": True,
            "message": "Transaction processed",
            "utr": utr,
            "matched": matched,
            "booking_id": booking_id,
            "latency_seconds": latency
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

