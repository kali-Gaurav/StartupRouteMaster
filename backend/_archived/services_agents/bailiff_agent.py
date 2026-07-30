import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Any
from sqlalchemy.orm import Session
from database.session import SessionLocal
from database.models import FraudAlert, BankTransaction, Booking, FinancialLedger, EscrowStatus
from services.ws_manager import ws_manager

logger = logging.getLogger("agent.bailiff")

class BailiffAgent:
    """
    [G2.1.1] The 'Bailiff' Auto-Void Agent.
    Autonomous Financial Enforcer: Monitors fraud alerts and neutralizes 
    pending/success transactions from banned identities.
    """
    def __init__(self):
        self.interval = 30  # Active scan every 30 seconds
        self.VOID_WINDOW_MINUTES = 15 # Only void transactions in this recent window

    async def pulse(self):
        """Active Pulse: listens for neutralization targets."""
        while True:
            try:
                await self.patrol_financial_perimeter()
            except Exception as e:
                logger.error(f"🚨 [BAILIFF] Patrol Failure: {e}")
            await asyncio.sleep(self.interval)

    async def patrol_financial_perimeter(self):
        """
        Scans FraudAlerts for new 'BANNED' statuses and nukes associated monetary assets.
        """
        db: Session = SessionLocal()
        try:
            # 1. Find recent BANNED identities from the last 15 minutes
            start_time = datetime.utcnow() - timedelta(minutes=self.VOID_WINDOW_MINUTES)
            new_alerts = db.query(FraudAlert).filter(
                FraudAlert.status == "BANNED",
                FraudAlert.created_at >= start_time,
                # Ensure we haven't processed this yet
                FraudAlert.metadata_json["bailiff_status"].astext == None
            ).all()

            if not new_alerts:
                return

            for alert in new_alerts:
                await self._neutralize_identity_assets(db, alert)

        finally:
            db.close()

    async def _neutralize_identity_assets(self, db: Session, alert: FraudAlert):
        """
        Identifies and voids all payments belonging to the banned identity.
        """
        identity = alert.metadata_json.get("identity")
        user_id = alert.user_id
        
        logger.warning(f"🏦 [BAILIFF] Neutralizing assets for Banned ID: {identity}")

        # 1. Discover Transactions (Child G2.1.1.2)
        txns = db.query(BankTransaction).filter(
            (BankTransaction.sender_phone == identity) | 
            (BankTransaction.id.in_(
                db.query(Booking.id).filter(Booking.user_id == user_id)
            ))
        ).filter(
            BankTransaction.status.in_(["MATCHED", "PROCESSING", "UNCLAIMED"]),
            BankTransaction.received_at >= datetime.utcnow() - timedelta(minutes=self.VOID_WINDOW_MINUTES)
        ).all()

        # 2. Collect Forensic Proof (Child G2.1.2.1)
        evidence_pack = await self._collect_forensic_evidence(db, identity, user_id)

        if not txns:
            logger.info(f"✅ [BAILIFF] No fluid assets found for {identity}. Archiving Evidence only.")
            alert.metadata_json = {
                **alert.metadata_json, 
                "bailiff_status": "PROCESSED_DRY",
                "evidence_pack": evidence_pack
            }
            db.commit()
            return

        for txn in txns:
            await self._execute_void(db, txn, reason=f"Fraud Block: {alert.alert_type}")

        # Finalize Alert Status with Evidence
        alert.metadata_json = {
            **alert.metadata_json, 
            "bailiff_status": "ASSETS_NEUTRALIZED",
            "evidence_pack": evidence_pack
        }
        db.commit()

    async def _collect_forensic_evidence(self, db: Session, identity: str, user_id: str) -> Dict[str, Any]:
        """
        Forensic Evidence Collector (Child G2.1.2.1).
        Bundles all known signals for possible dispute resolution.
        """
        from database.models import RouteSearchLog, IdentityFingerprint
        
        # 1. Fingerprint History
        fingerprints = db.query(IdentityFingerprint).filter(
            (IdentityFingerprint.ip_address == identity) | 
            (IdentityFingerprint.fingerprint_hash == identity) |
            (IdentityFingerprint.user_id == user_id)
        ).all()
        
        # 2. Recent Search Pattern (Velocity Check)
        search_logs = db.query(RouteSearchLog).filter(
            (RouteSearchLog.ip_address == identity) |
            (RouteSearchLog.user_id == user_id)
        ).order_by(RouteSearchLog.created_at.desc()).limit(10).all()

        return {
            "forensics_timestamp": str(datetime.utcnow()),
            "identity_id": identity,
            "fingerprints": [
                {
                    "hash": f.fingerprint_hash,
                    "ip": f.ip_address,
                    "ua": f.user_agent,
                    "risk": f.risk_score
                } for f in fingerprints
            ],
            "search_velocity": [
                {
                    "src": s.src,
                    "dst": s.dst,
                    "at": str(s.created_at)
                } for s in search_logs
            ],
            "verdict_reason": "Autonomous Neutralization based on Cluster Anomaly"
        }

    async def _execute_void(self, db: Session, txn: BankTransaction, reason: str):
        """
        Autonomous Voiding Engine (Child G2.1.1.3).
        Issues a refund or system Void to prevent settlement.
        """
        old_status = txn.status
        txn.status = "VOIDED_BY_BAILIFF"
        txn.raw_payload = f"{txn.raw_payload} | [VOIDED_BY_BAILIFF] {datetime.utcnow()} REASON: {reason}"
        
        # 1. Sync with Booking if exists
        booking = db.query(Booking).filter(Booking.utr_number == txn.utr_number).first()
        if booking:
            booking.escrow_status = EscrowStatus.FAILED
            booking.escrow_message = f"🚫 VOIDED: {reason}"
            logger.critical(f"💥 [BAILIFF] VOIDED Booking {booking.id} due to Fraud Link.")

        # 2. Record Financial Recovery in Ledger (Final Audit)
        from services.ledger_service import ledger_service
        await ledger_service.record_transaction(
            db,
            amount=txn.amount,
            source_account="CASH_ESCROW" if old_status == "MATCHED" else "SUSPENSE_LIMBO",
            destination_account="FRAUD_RECOVERY_POOL",
            reference_id=f"VOID_{txn.utr_number}",
            description=f"Autonomous Fraud Neutralization for UTR {txn.utr_number}"
        )
        
        # 3. Broadcast Success
        await ws_manager.broadcast_global(
            f"💰 [BAILIFF] Autonomous VOID Successful ($ {txn.amount} recovered from Fraud).",
            "FINANCE_ALERT"
        )
        
        logger.info(f"🛡️ [BAILIFF] Transaction {txn.utr_number} neutralized and moved to Recovery Pool.")

bailiff_agent = BailiffAgent()
