import logging
from datetime import datetime, timedelta
from sqlalchemy.orm import Session
from database.models import CommissionTracking, AgentWallet, Booking, User, AuditLog

logger = logging.getLogger("commission-service")

AGENT_BASE_COMMISSION = 10.0
TOP_AGENT_THRESHOLD = 50 # Bookings per week
TOP_AGENT_COMMISSION = 12.0

class CommissionService:
    @staticmethod
    def record_commission(db: Session, booking_id: str, agent_id: str) -> CommissionTracking:
        """
        [Task 44.2] Records a new pending commission for an agent.
        """
        # 1. Performance Multiplier check
        one_week_ago = datetime.utcnow() - timedelta(days=7)
        weekly_count = db.query(CommissionTracking).filter(
            CommissionTracking.user_id == agent_id,
            CommissionTracking.created_at >= one_week_ago
        ).count()
        
        rate = TOP_AGENT_COMMISSION if weekly_count >= TOP_AGENT_THRESHOLD else AGENT_BASE_COMMISSION
        
        # 2. Create Ledger Entry
        track = CommissionTracking(
            user_id=agent_id,
            booking_id=booking_id,
            amount=rate,
            status="PENDING"
        )
        db.add(track)
        
        # 3. Update Wallet Pending Balance
        wallet = db.query(AgentWallet).filter(AgentWallet.user_id == agent_id).with_for_update().first()
        if not wallet:
            wallet = AgentWallet(user_id=agent_id)
            db.add(wallet)
        
        wallet.pending_commission += rate
        
        db.commit()
        logger.info(f"Commission Recorded: Agent {agent_id} | Amount: ₹{rate} | PENDING")
        return track

    @staticmethod
    def settle_batch(db: Session, agent_id: str):
        """
        [Task 44.4] Moves PENDING commissions to total_earned for an agent.
        Safely transfers from Escrow to Wallet state.
        """
        pending_tracks = db.query(CommissionTracking).filter(
            CommissionTracking.user_id == agent_id,
            CommissionTracking.status == "PENDING"
        ).with_for_update().all()
        
        if not pending_tracks: return
        
        total_to_settle = sum(t.amount for t in pending_tracks)
        wallet = db.query(AgentWallet).filter(AgentWallet.user_id == agent_id).with_for_update().first()
        
        # Atomic Shift
        wallet.pending_commission -= total_to_settle
        wallet.total_earned += total_to_settle
        wallet.last_payout_at = datetime.utcnow()
        
        payout_batch_id = f"PAY_{datetime.utcnow().strftime('%Y%m%d')}_{uuid.uuid4().hex[:6]}"
        
        for t in pending_tracks:
            t.status = "SETTLED"
            t.settled_at = datetime.utcnow()
            t.payout_id = payout_batch_id
            
        db.commit()
        logger.info(f"Settled ₹{total_to_settle} for Agent {agent_id} in batch {payout_batch_id}")

commission_service = CommissionService()
import uuid
