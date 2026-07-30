import logging
import asyncio
from typing import List, Dict, Any
from services.agents.base_agent import BaseAgent, AgentPriority
from database.session import SessionLocal
from database.models import Booking
from services.ws_manager import ws_manager

logger = logging.getLogger("agent.social_ingestor")

class SocialIngestorAgent(BaseAgent):
    """
    [G3.4.1] The 'Travel Pulse' Social Ingestor.
    Monitors external news/social channels for disruptions before they hit official APIs.
    Dispatches crisis alerts to affected passengers.
    """
    name = "SocialIngestorAgent"
    description = "Early-warning system for rail disruptions via social/news scraping."
    category = "intelligence"
    priority = AgentPriority.NORMAL
    icon = "📡"
    color = "#F97316" # Orange

    async def pulse(self):
        """Continuous scrape pulse."""
        while True:
            if not self.is_paused:
                try:
                    await self.monitor_disruptions()
                except Exception as e:
                    logger.error(f"⚠️ [SOCIAL] Monitor Error: {e}")
            await asyncio.sleep(300) # Every 5 minutes

    async def monitor_disruptions(self):
        """
        [Child G3.4.1.1 & G3.4.1.2]
        Scrapes and Classifies incoming 'crisis' signals.
        """
        # 1. Scrape Signals (Child G3.4.1.1)
        signals = await self._scrape_latest_news()
        
        for signal in signals:
            # 2. Extract Entities (Child G3.4.1.2) - Mocked ML
            train_num = signal.get("extracted_train")
            station = signal.get("extracted_station")
            severity = signal.get("severity", "MEDIUM")
            
            if train_num or station:
                logger.warning(f"🚨 [SOCIAL] DISRUPTION DETECTED: {signal['text']} (Train: {train_num}, Station: {station})")
                
                # 3. Crisis Notification (Child G3.4.1.3)
                await self._notify_impacted_users(train_num, station, signal['text'], severity)

    async def _scrape_latest_news(self) -> List[Dict[str, Any]]:
        """Mocked RSS/News Scraper."""
        # Conceptually queries Twitter API or RSS feeds
        return [
            # Example Signal
            {"text": "Severe fog causing cancellations for 12259 Duronto", "extracted_train": "12259", "severity": "HIGH"}
        ]

    async def _notify_impacted_users(self, train_num: str, station: str, message: str, severity: str):
        """
        Identifies users with active bookings and sends high-priority alerts.
        """
        db = SessionLocal()
        try:
            # Find users booked on this train or station in the next 24h
            # Simplified query for now
            impacted_bookings = db.query(Booking).filter(
                Booking.status == "CONFIRMED"
            ).all()
            
            for booking in impacted_bookings:
                # Actual logic: check if booking.train_number == train_num
                logger.info(f"📤 [SOCIAL] Dispatching Crisis Alert to User {booking.user_id}")
                
                alert = {
                    "type": "CRISIS_ALERT",
                    "title": "Early Disruption Advisory",
                    "message": message,
                    "severity": severity,
                    "action": "CHECK_ALTERNATIVES"
                }
                await ws_manager.send_to_user(booking.user_id, alert, "CRITICAL")
                
        finally:
            db.close()

social_ingestor_agent = SocialIngestorAgent()
