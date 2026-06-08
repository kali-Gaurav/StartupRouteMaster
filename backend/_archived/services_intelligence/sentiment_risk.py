import logging
from typing import Dict, Any, List
from core.infrastructure.redis_manager import async_redis_client

logger = logging.getLogger("nexus.sentiment")

class SentimentRiskService:
    """
    [RM-ML-301] Sentiment-Risk Fusion Engine.
    Fuses qualitative user reviews with quantitative safety telemetry.
    """
    
    SENTIMENT_KEY_PREFIX = "station_sentiment:"

    @staticmethod
    async def ingest_vibe_review(station_code: str, sentiment_text: str, score: float):
        """
        Record a user's 'Safety Vibe' review and update the aggregate sentiment.
        """
        # 1. Simple Sentiment weighting (Industry Grade uses BERT/RoBERTa here)
        # Mocking the AI sentiment extraction
        is_negative = any(word in sentiment_text.lower() for word in ["dark", "empty", "shady", "unsafe", "scary"])
        
        sentiment_delta = -15 if is_negative else 5
        
        current_sentiment = await async_redis_client.get(f"{SentimentRiskService.SENTIMENT_KEY_PREFIX}{station_code}")
        new_total = max(0, min(100, (float(current_sentiment) if current_sentiment else 80) + sentiment_delta))
        
        await async_redis_client.set(f"{SentimentRiskService.SENTIMENT_KEY_PREFIX}{station_code}", str(new_total))
        
        logger.info(f"🎭 [SENTIMENT] Station {station_code} vibe updated: {new_total} (Delta: {sentiment_delta})")
        
        # 2. Trigger Alarm if sentiment drops below threshold
        if new_total < 40:
            await SentimentRiskService._trigger_safety_audit(station_code, "CRITICAL_SENTIMENT_DROP")

    @staticmethod
    async def get_fused_risk_score(station_code: str) -> float:
        """
        Calculate the 'Fused Risk Score' by combining Vibe, Sathi Presence, and Sentiment.
        """
        from services.safety_intelligence_service import SafetyIntelligenceService
        
        intelligence = await SafetyIntelligenceService.predict_station_risk(station_code)
        sentiment_raw = await async_redis_client.get(f"{SentimentRiskService.SENTIMENT_KEY_PREFIX}{station_code}")
        sentiment_score = float(sentiment_raw) if sentiment_raw else 80.0
        
        # Formula: 70% Telemetry + 30% Sentiment
        fused_score = (intelligence["risk_score"] * 0.7) + ((100 - sentiment_score) * 0.3)
        
        return round(fused_score, 2)

    @staticmethod
    async def _trigger_safety_audit(station_code: str, reason: str):
        """
        Automated request for a Sathi patrol based on negative sentiment trends.
        """
        logger.warning(f"🚨 [SENTIMENT] Proactive Audit requested for {station_code}. Reason: {reason}")
        # In production: Creates a 'SOFT_DISPATCH' task for the nearest Sathi.
