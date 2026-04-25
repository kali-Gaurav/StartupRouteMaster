from ast import Dict
import hmac
import hashlib
import logging
import time
from typing import Optional, Any, Dict, List
from sqlalchemy.orm import Session
from database.models import FinancialLedger, AuditLog

logger = logging.getLogger("routemaster.sentinel")

class HealthSentinel:
    """
    [Task 4.1] Global Signal Sentinel.
    Monitors provider health across all search and booking requests.
    """
    def __init__(self):
        self.provider_metrics: Dict[str, List[Dict[str, Any]]] = {}
        self.identity_risk: Dict[str, List[Dict[str, Any]]] = {}
        self.MAX_SAMPLES = 50
        self.LATENCY_THRESHOLD = 500 # ms
        self.ERROR_THRESHOLD = 0.05 # 5%

    def record_signal(self, provider: str, latency: float, success: bool):
        """Records a single telemetry signal for a provider."""
        if provider not in self.provider_metrics:
            self.provider_metrics[provider] = []
        
        metrics = self.provider_metrics[provider]
        metrics.append({
            "latency": latency,
            "success": success,
            "ts": time.time()
        })
        
        # Keep only the moving window
        if len(metrics) > self.MAX_SAMPLES:
            self.provider_metrics[provider] = metrics[-self.MAX_SAMPLES:]

    def record_identity_signal(self, identity_id: str, success: bool):
        """[Task 6.1] Records suspicious behavior signals for specific IPs/Fingerprints."""
        if identity_id not in self.identity_risk:
            self.identity_risk[identity_id] = []
        
        history = self.identity_risk[identity_id]
        history.append({
            "success": success,
            "ts": time.time()
        })
        
        if len(history) > self.MAX_SAMPLES:
            self.identity_risk[identity_id] = history[-self.MAX_SAMPLES:]

    def get_identity_risk_score(self, identity_id: str) -> float:
        """Calculates a risk score based on recent failure clusters."""
        history = self.identity_risk.get(identity_id, [])
        if not history or len(history) < 10:
            return 0.0
            
        failures = sum(1 for h in history if not h["success"])
        return failures / len(history)

    def get_status(self, provider: str) -> str:
        """Determines the current health state of a provider."""
        metrics = self.provider_metrics.get(provider, [])
        if not metrics or len(metrics) < 5:
            return "HEALTHY" # Need baseline data
            
        avg_latency = sum(m["latency"] for m in metrics) / len(metrics)
        error_rate = sum(1 for m in metrics if not m["success"]) / len(metrics)
        
        if avg_latency > self.LATENCY_THRESHOLD or error_rate > self.ERROR_THRESHOLD:
            logger.warning(f"⚠️ [SENTINEL] Provider {provider} DEGRADED | Lat: {avg_latency:.0f}ms | Err: {error_rate:.1%}")
            return "DEGRADED"
            
        return "HEALTHY"

    def should_bypass_live_provider(self, provider: str) -> bool:
        """
        [Task 4.1] Safety Switch: Tells the engine to skip live lookup and use cache.
        """
        status = self.get_status(provider)
        return status == "DEGRADED"

    def get_provider_latency(self, provider: str) -> float:
        metrics = self.provider_metrics.get(provider, [])
        if not metrics: return 0.0
        return sum(m["latency"] for m in metrics) / len(metrics)

    def report_system_event(self, event_type: str, severity: str, details: Dict[str, Any]):
        """Logs and stores a system-level event from gateway failover or infrastructure changes."""
        logger.warning(f"[SENTINEL_EVENT] {event_type} | {severity} | {details}")
        self.provider_metrics.setdefault("system_events", []).append({
            "event_type": event_type,
            "severity": severity,
            "details": details,
            "ts": time.time()
        })

health_sentinel = HealthSentinel()

class SentinelService:
    # [Rest of SentinelService logic stays the same]
    @staticmethod
    async def calculate_row_hash(data: str, previous_hash: str) -> str:
        """
        [Project Sentinel] Creates a cryptographically linked hash using the dynamic Nexus secret.
        """
        from core.nexus.financial.signer import ledger_signer
        payload = f"{data}|{previous_hash}"
        # We use the generate_signature logic which uses the fingerprint-isolated secret
        return await ledger_signer.generate_signature(0, payload)

    @staticmethod
    async def seal_ledger_entry(db: Session, entry: FinancialLedger):
        """
        [Project Sentinel] Seals a new ledger entry by chaining it to the previous row.
        """
        # 1. Find the last sealed entry
        last_entry = db.query(FinancialLedger).filter(
            FinancialLedger.id < entry.id
        ).order_by(FinancialLedger.id.desc()).first()

        prev_hash = last_entry.cumulative_hash if last_entry else "GENESIS_BLOCK"
        
        # 2. Serialize entry data for hashing
        data_str = f"{entry.transaction_uuid}:{entry.amount}:{entry.debit_account}:{entry.credit_account}"
        
        # 3. Calculate and set hashes
        entry.previous_row_hash = prev_hash  # type: ignore
        entry.cumulative_hash = await SentinelService.calculate_row_hash(data_str, prev_hash)  # type: ignore
        
        db.commit()
        logger.info(f"⚓ Ledger entry {entry.id} SEALED with hash {entry.cumulative_hash[:8]}...")

    @staticmethod
    async def verify_chain_integrity(db: Session) -> Dict[str, Any]:
        """
        Full audit of the FinancialLedger chain.
        Detects tampering or row deletions.
        """
        entries = db.query(FinancialLedger).order_by(FinancialLedger.id).all()
        current_prev_hash = "GENESIS_BLOCK"
        tampered_ids = []

        for entry in entries:
            # Re-calculate
            data_str = f"{entry.transaction_uuid}:{entry.amount}:{entry.debit_account}:{entry.credit_account}"
            expected_hash = await SentinelService.calculate_row_hash(data_str, entry.previous_row_hash)  # type: ignore
            
            if entry.cumulative_hash != expected_hash or entry.previous_row_hash != current_prev_hash:  # type: ignore
                tampered_ids.append(entry.id)
                logger.error(f"🚨 TAMPER DETECTED: Ledger ID {entry.id} mismatch!")
            
            current_prev_hash = entry.cumulative_hash  # type: ignore

        return {
            "is_clean": len(tampered_ids) == 0,
            "tampered_rows": tampered_ids,
            "total_rows": len(entries)
        }
