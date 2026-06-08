import re
import logging
import json
import base64
import asyncio
from collections import deque
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend
from datetime import datetime
from typing import Optional, Dict, Any, Tuple
from sqlalchemy.orm import Session
from database.models import BankTransaction, Booking, EscrowStatus
from services.cache_service import cache_service
from schemas.bank_webhook import BankSMSPayload
from config import Config
from core.resilience.core import circuit_breaker_manager, CircuitBreaker, CircuitConfig
from core.resilience.retry import RetryPolicy

logger = logging.getLogger(__name__)

from services.ws_manager import ws_manager


class BankWebhookServiceMetrics:
    """Metrics tracking for bank webhook service."""
    
    def __init__(self):
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = asyncio.Lock()
        self._circuit_states: Dict[str, str] = {}
    
    async def record_transaction(self, success: bool, utr: str, processing_time_ms: float):
        """Record transaction metrics."""
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": datetime.utcnow(),
                "success": success,
                "utr": utr,
                "processing_time_ms": processing_time_ms
            })
    
    async def record_circuit_state(self, circuit_name: str, state: str):
        """Record circuit breaker state change."""
        self._circuit_states[circuit_name] = state
    
    def get_metrics(self) -> dict:
        """Get service metrics."""
        if not self._metrics:
            return {"total_transactions": 0, "success_rate": 0.0}
        
        total = len(self._metrics)
        successful = sum(1 for m in self._metrics if m["success"])
        processing_times = [m["processing_time_ms"] for m in self._metrics]
        
        return {
            "total_transactions": total,
            "successful_transactions": successful,
            "failed_transactions": total - successful,
            "success_rate": successful / total if total > 0 else 0.0,
            "avg_processing_time_ms": sum(processing_times) / len(processing_times) if processing_times else 0.0,
            "circuit_states": self._circuit_states.copy()
        }


class BankWebhookService:
    """
    Task 2 & 3: Real-Time Bank SMS/Webhook Integration.
    Handles SMS parsing, UTR deduplication, and transaction matching.
    
    Enhanced with resilience patterns: circuit breakers, retry policies, and metrics tracking.
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

    def __init__(self, db: Session):
        self.db = db
        
        # Circuit breakers for external service calls
        self._kafka_breaker = circuit_breaker_manager.get_or_create(
            "bank_webhook_kafka",
            CircuitConfig(failure_threshold=5, timeout_seconds=30.0, success_threshold=2)
        )
        self._fraud_breaker = circuit_breaker_manager.get_or_create(
            "bank_webhook_fraud",
            CircuitConfig(failure_threshold=3, timeout_seconds=15.0, success_threshold=2)
        )
        self._ledger_breaker = circuit_breaker_manager.get_or_create(
            "bank_webhook_ledger",
            CircuitConfig(failure_threshold=5, timeout_seconds=30.0, success_threshold=2)
        )
        self._cache_breaker = circuit_breaker_manager.get_or_create(
            "bank_webhook_cache",
            CircuitConfig(failure_threshold=10, timeout_seconds=10.0, success_threshold=3)
        )
        
        # Retry policies
        self._kafka_retry = RetryPolicy(
            max_attempts=3,
            initial_delay=0.5,
            max_delay=10.0,
            conditions=[
                lambda e: "timeout" in str(e).lower(),
                lambda e: "connection" in str(e).lower(),
                lambda e: hasattr(e, 'status') and e.status >= 500
            ]
        )
        self._fraud_retry = RetryPolicy(
            max_attempts=3,
            initial_delay=0.5,
            max_delay=5.0,
            conditions=[
                lambda e: "timeout" in str(e).lower()
            ]
        )
        
        # Metrics tracking
        self._metrics = BankWebhookServiceMetrics()
        
        logger.info("BankWebhookService initialized with resilience patterns")

    def decrypt_payload(self, ciphertext_b64: str, iv_b64: Optional[str]) -> str:
        """Task 2.7: End-to-end encryption for SMS data payload using AES-256-CBC."""
        try:
            if not iv_b64:
                raise ValueError("Missing IV for encrypted SMS payload")

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

        # 1. Safety Latch: System Integrity Check with circuit breaker
        async def check_financial_lock():
            return await cache_service.get("PLATFORM_FINANCIAL_LOCK")
        
        try:
            platform_locked = await self._cache_breaker.execute(check_financial_lock)
            if platform_locked:
                logger.critical(f"🛑 [INGESTION] BLOCKED: System in Emergency Lock. UTR: {utr}")
                return {"success": False, "message": "System temporarily suspended for audit."}
        except Exception as e:
            logger.error(f"Failed to check financial lock: {e}")
            # Fail open for safety latch - continue processing

        # 2. Fraud Screening [Task 3.1] with circuit breaker and retry
        async def fraud_check():
            from services.fraud_detection_service import fraud_service
            return fraud_service.validate_utr_advanced(
                db,
                utr,
                payload.device_id or "unknown_device",
                None,
                payload.device_id
            )
        
        try:
            is_safe, fraud_msg = await self._fraud_breaker.execute(
                self._fraud_retry.execute,
                fraud_check
            )
            if not is_safe:
                logger.warning(f"🚨 [INGESTION] Fraud Blocked: {utr} | Reason: {fraud_msg}")
                return {"success": False, "message": fraud_msg}
        except Exception as e:
            logger.error(f"Fraud check failed: {e}")
            # Fail open - allow processing but log warning
            logger.warning(f"⚠️ [INGESTION] Fraud check failed, proceeding with caution: {utr}")

        # 2.4 Duplicate UTR filtering with circuit breaker
        dedup_key = f"bank_utr_dedup:{utr}"

        async def check_dedup():
            return cache_service.get(dedup_key)

        async def set_dedup():
            cache_service.set(dedup_key, "1", ttl_seconds=86400)

        try:
            is_duplicate = await self._cache_breaker.execute(check_dedup)
            if is_duplicate:
                return {"success": False, "message": "Duplicate UTR", "utr": utr}
            await self._cache_breaker.execute(set_dedup)
        except Exception as e:
            logger.error(f"Duplicate check failed: {e}")
            # Continue without deduplication on cache failure

        # 2.5 VPA Blacklist Check [Task 28.1]
        sender_vpa = payload.sender  # Assuming sender identifier for now
        is_blacklisted = False
        try:
            models_module = __import__("database.models", fromlist=["VPABlacklist"])
            if hasattr(models_module, "VPABlacklist"):
                VPABlacklist = getattr(models_module, "VPABlacklist")
                is_blacklisted = db.query(VPABlacklist).filter(VPABlacklist.vpa == sender_vpa).first() is not None
        except Exception:
            is_blacklisted = False

        if is_blacklisted:
            logger.critical(f"🛑 [INGESTION] Blacklisted VPA Attempt: {sender_vpa}")
            return {"success": False, "message": "VPA blacklisted due to suspicious activity."}

        # --- [Task 4.3] Kafka Ingestion Transition with circuit breaker and retry
        from services.event_producer import publish_payment_ingested
        
        async def publish_to_kafka():
            return await publish_payment_ingested(
                utr=utr,
                amount=amount or 0.0,
                currency="INR",
                sender_vpa=sender_vpa,
                fingerprint_id=payload.device_id,
                raw_payload={"body": sms_body, "sender": payload.sender, "receive_time": str(receive_time)}
            )
        
        try:
            ingested = await self._kafka_breaker.execute(
                self._kafka_retry.execute,
                publish_to_kafka
            )

            if ingested:
                logger.info(f"📤 [BACKBONE] Payment {utr} published for async processing.")
                return {
                    "success": True, 
                    "message": "Payment received and queued for processing.",
                    "utr": utr,
                    "status": "INGESTED_TO_BACKBONE"
                }
            else:
                logger.error(f"❌ [BACKBONE] Failed to publish payment {utr} to Kafka.")
                return {"success": False, "message": "Internal processing queue failed."}
        except Exception as e:
            logger.error(f"Kafka publish failed: {e}")
            return {"success": False, "message": "Internal processing queue failed."}

    async def process_payment_signal(self, utr: str, amount: float, vpa: str, fingerprint_id: str, raw_data: dict) -> Dict[str, Any]:
        """
        [Task 4.3] Asynchronous Payment Processor.
        Invoked by the IngestionWorker to finalize transactions in the ledger.
        """
        db = self.db # Assuming self.db is set or passed
        receive_time = datetime.utcnow()
        sms_body = raw_data.get("body", "")

        # 1. Create Transaction Record
        txn = BankTransaction(
            utr_number=utr,
            amount=amount or 0.0,
            bank_name=vpa,
            raw_payload=sms_body,
            sender_phone=fingerprint_id,
            received_at=receive_time,
            status="PROCESSING"
        )
        db.add(txn)
        
        matched = False
        booking_id = None
        booking = None
        
        # 2. Binary Matching (Short-ID/UTR/Cent-Matching)
        short_id_match = re.search(r"RM_(?P<sid>[A-Z0-9]{8})", sms_body)
        if short_id_match:
            sid = short_id_match.group("sid")
            booking = db.query(Booking).filter(Booking.id.like(f"{sid.lower()}%"), Booking.escrow_status.in_([EscrowStatus.CREATED, EscrowStatus.UTR_SUBMITTED])).first()
        
        if not booking:
            booking = db.query(Booking).filter(Booking.utr_number == utr, Booking.escrow_status == EscrowStatus.UTR_SUBMITTED).first()

        if not booking and amount:
            booking = db.query(Booking).filter(Booking.amount_paid == amount, Booking.escrow_status == EscrowStatus.CREATED).order_by(Booking.created_at.desc()).first()

        if booking:
            # 3. Sealed Ledger Recording [SENTINEL PROTECTED]
            from services.ledger_service import ledger_service
            ledger_entry = await ledger_service(db).record_transaction(
                db,
                amount=amount,
                source_account="BANK_LIQUIDITY",
                destination_account="CASH_ESCROW",
                reference_id=f"B_{booking.id}",
                description=f"Kafka-Matched Income for Booking {booking.id}"
            )

            # 4. Finalize Booking Status
            booking.escrow_status = EscrowStatus.VERIFIED
            booking.utr_number = utr
            booking.escrow_message = f"✅ Verified via Async Ledger (Tx: {ledger_entry.transaction_uuid[:8]})"
            txn.status = "MATCHED"
            matched = True
            booking_id = str(booking.id)
            
            from services.merchant_vpa_service import merchant_vpa_service
            if booking.merchant_vpa:
                merchant_vpa_service.record_volume(booking.merchant_vpa, booking.amount_paid)

            from services.fraud_detection_service import fraud_service
            fraud_service.clear_lockout(fingerprint_id)

            await ws_manager.broadcast_log(booking_id, "✅ Payment Secured (Async)!", "VERIFIED")
        else:
            # 5. Financial Limbo Fallback
            from database.models import UnclaimedTransaction
            unclaimed = UnclaimedTransaction(
                utr_number=utr,
                amount=amount or 0.0,
                bank_name=vpa,
                raw_payload=sms_body,
                status="UNCLAIMED"
            )
            db.add(unclaimed)
            
            from services.ledger_service import ledger_service
            await ledger_service(db).record_transaction(
                db,
                amount=amount or 0.0,
                source_account="BANK_LIQUIDITY",
                destination_account="SUSPENSE_LIMBO",
                reference_id=f"UTR_{utr}",
                description=f"Unclaimed Kafka Payment (UTR: {utr})"
            )
        
        db.commit()
        return {"success": True, "matched": matched, "booking_id": booking_id}

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
                    timestamp=datetime.utcnow(),
                    device_id=None,
                    is_encrypted=False,
                    iv=None,
                    status=None
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

# =========================================================================
    # RESILIENCE PATTERNS
    # =========================================================================

    def get_metrics(self) -> dict:
        """Get service metrics."""
        return self._metrics.get_metrics()

    def health_check(self) -> dict:
        """Check service health."""
        return {
            "status": "healthy",
            "circuit_breakers": {
                "kafka": self._kafka_breaker.get_metrics(),
                "fraud": self._fraud_breaker.get_metrics(),
                "ledger": self._ledger_breaker.get_metrics(),
                "cache": self._cache_breaker.get_metrics()
            },
            "metrics": self._metrics.get_metrics()
        }

    def reset_circuit_breakers(self):
        """Reset all circuit breakers."""
        self._kafka_breaker.reset()
        self._fraud_breaker.reset()
        self._ledger_breaker.reset()
        self._cache_breaker.reset()
        logger.info("All circuit breakers reset for bank_webhook_service")
