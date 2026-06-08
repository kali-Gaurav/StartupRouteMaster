import logging
from datetime import datetime
from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from database.models import FraudAlert, IdentityFingerprint
from services.sentinel_service import health_sentinel
from services.ws_manager import ws_manager
from services.agents.base_agent import BaseAgent, AgentPriority
from database.session import SessionLocal

logger = logging.getLogger("agents.security")

class SecurityGuardianAgent(BaseAgent):
    """
    [Group 1] The 'Shield' Security Guardian.
    Autonomously monitors identity-risk clusters and issues network-layer blocks.
    """
    name = "SecurityGuardian"
    description = "Monitors traffic guardian telemetry and neutralizes high-risk identities"
    category = "security"
    priority = AgentPriority.HIGH
    icon = "🛡️"
    color = "#EF4444" # Red
    version = "2.0.0"
    auto_schedule_interval = 300 # Every 5 minutes

    def __init__(self):
        super().__init__()
        self.CRITICAL_RISK_THRESHOLD = 0.8 # 80% failure rate triggers block

    async def execute(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Main execution hook for the agent swarm.
        """
        results = await self.monitor_threat_landscape()
        return {
            "status": "success",
            "summary": f"Neutralized {len(results)} high-risk identities",
            "data": {
                "neutralized_count": len(results),
                "neutralized_identities": results
            }
        }

    async def monitor_threat_landscape(self) -> List[str]:
        """
        Scans HealthSentinel for dangerous identities and neutralizes them.
        """
        logger.info("🛡️ [SHIELD] Monitoring traffic guardian telemetry...")
        
        high_risk_identities = [
            identity_id for identity_id, history in health_sentinel.identity_risk.items()
            if health_sentinel.get_identity_risk_score(identity_id) >= self.CRITICAL_RISK_THRESHOLD
        ]

        neutralized = []
        for identity_id in high_risk_identities:
            await self._neutralize_identity(identity_id)
            neutralized.append(identity_id)
        
        return neutralized

    async def _neutralize_identity(self, identity_id: str):
        """
        Issues an autonomous block command for a high-risk identity.
        """
        risk_score = health_sentinel.get_identity_risk_score(identity_id)
        logger.critical(f"🚩 [SHIELD] NEUTRALIZING High-Risk Identity: {identity_id} | Risk: {risk_score:.2%}")

        with SessionLocal() as db:
            # 1. Update Identity Trust in DB
            fingerprint = db.query(IdentityFingerprint).filter(
                (IdentityFingerprint.ip_address == identity_id) | 
                (IdentityFingerprint.fingerprint_hash == identity_id)
            ).first()

            if fingerprint:
                fingerprint.is_trusted = False
                fingerprint.risk_score = risk_score
            
            # 2. Log Fraud Alert
            alert = FraudAlert(
                user_id=fingerprint.user_id if fingerprint else None,
                alert_type="TRAFFIC_CLUSTER_ANOMALY",
                severity="CRITICAL",
                status="BANNED",
                metadata_json={
                    "identity": identity_id,
                    "risk_score": risk_score,
                    "reason": "Automated Block via Security Guardian"
                }
            )
            db.add(alert)
            db.commit()

        # 3. Broadcast Security Alert to Admins
        await ws_manager.broadcast_global(
            f"🚫 [SHIELD] Autonomous block issued for {identity_id}. Risk score: {risk_score:.1%}",
            "SECURITY_ALERT"
        )
        
        # 4. (Future) Trigger Firewall/Guardian commands via external API

def get_security_guardian():
    return SecurityGuardianAgent()
