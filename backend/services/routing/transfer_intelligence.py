"""
Transfer Intelligence Score (TIS) Service

Calculates reliability scores for transfer points based on historical data.
Ranks transfer connections by likelihood of successful connection.
"""

import logging
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional, Tuple
from collections import defaultdict

from backend.services.route_engine import RouteEngine, Journey, RouteSegment

logger = logging.getLogger(__name__)


class RiskLevel(str, Enum):
    """Risk classification for transfer connections"""
    LOW = "low"        # 80%+ connection success rate
    MEDIUM = "medium"  # 60-80% connection success rate
    HIGH = "high"      # < 60% connection success rate
    UNKNOWN = "unknown"  # Insufficient data


@dataclass
class TransferScore:
    """
    Transfer intelligence score for a single transfer point.
    
    Attributes:
    - transfer_station: Station where transfer occurs
    - arrival_train: Train arriving at transfer station
    - departure_train: Train departing from transfer station
    - connection_time_minutes: Time between arrival and departure
    - tis_score: Transfer Intelligence Score (0-100)
    - risk_level: Risk classification
    - historical_success_rate: Historical on-time connection rate
    - factors: Breakdown of contributing factors
    """
    transfer_station: str
    arrival_train: str
    departure_train: str
    connection_time_minutes: int
    tis_score: float
    risk_level: RiskLevel
    historical_success_rate: float
    factors: Dict[str, float] = field(default_factory=dict)
    recommendation: str = ""
    timestamp: datetime = field(default_factory=datetime.utcnow)


@dataclass
class JourneyTransferScore:
    """
    Overall transfer intelligence for a complete journey.
    """
    journey: Journey
    overall_score: float  # Weighted average of all transfer scores
    risk_level: RiskLevel
    transfer_details: List[TransferScore]
    recommendations: List[str]
    timestamp: datetime = field(default_factory=datetime.utcnow)


class TransferIntelligenceService:
    """
    Service for calculating Transfer Intelligence Scores (TIS).
    
    Features:
    - Historical on-time percentage for connecting trains
    - Risk level classification (LOW/MEDIUM/HIGH)
    - Integration with route ranking algorithm
    - Visual indicator data for UI
    
    Data Sources:
    - Historical booking and travel data
    - Train delay statistics
    - Station buffer time data
    """
    
    # Historical connection success rates (would be loaded from DB in production)
    # Format: (arrival_station, departure_station) -> success_rate
    CONNECTION_SUCCESS_RATES = {
        ("NDLS", "BCT"): 0.88,
        ("NDLS", "MAS"): 0.82,
        ("BCT", "NDLS"): 0.85,
        ("BCT", "ADI"): 0.78,
        ("MAS", "NDLS"): 0.80,
        ("MAS", "BLR"): 0.75,
        ("BLR", "MAS"): 0.72,
        ("CNB", "NDLS"): 0.76,
        ("NDLS", "CNB"): 0.79,
        ("ADI", "BCT"): 0.74,
        ("JAI", "NDLS"): 0.71,
        ("DDN", "NDLS"): 0.68,
        ("GWL", "NDLS"): 0.65,
        ("BPL", "NDLS"): 0.62,
    }
    
    # Station buffer time requirements (minutes)
    # Major stations need more buffer due to complexity
    STATION_BUFFER_REQUIREMENTS = {
        "NDLS": 25,
        "BCT": 20,
        "MAS": 20,
        "BLR": 15,
        "CNB": 15,
        "ADI": 15,
        "JAI": 12,
        "DDN": 12,
        "GWL": 10,
        "BPL": 10,
    }
    
    # Default buffer for unknown stations
    DEFAULT_BUFFER = 15
    
    # Risk thresholds
    RISK_THRESHOLD_LOW = 0.80
    RISK_THRESHOLD_MEDIUM = 0.60
    
    def __init__(self, route_engine: Optional[RouteEngine] = None):
        self.route_engine = route_engine or RouteEngine()
        self._cache: Dict[str, TransferScore] = {}
        self._station_stats: Dict[str, Dict[str, Any]] = {}
    
    async def calculate_transfer_score(
        self,
        transfer_station: str,
        arrival_train: str,
        departure_train: str,
        connection_time_minutes: int,
        travel_date: Optional[str] = None
    ) -> TransferScore:
        """
        Calculate TIS for a single transfer point.
        
        Args:
            transfer_station: Station code where transfer occurs
            arrival_train: Train number arriving at transfer station
            departure_train: Train number departing from transfer station
            connection_time_minutes: Time between arrival and departure
            travel_date: Optional travel date for date-specific scoring
            
        Returns:
            TransferScore with TIS and risk classification
        """
        cache_key = f"{transfer_station}-{arrival_train}-{departure_train}-{travel_date}"
        
        # Check cache
        if cache_key in self._cache:
            return self._cache[cache_key]
        
        # Calculate individual factors
        buffer_factor = self._calculate_buffer_factor(
            transfer_station, connection_time_minutes
        )
        historical_factor = self._calculate_historical_factor(
            transfer_station, arrival_train, departure_train
        )
        train_factor = self._calculate_train_factor(arrival_train, departure_train)
        time_factor = self._calculate_time_factor(connection_time_minutes)
        
        # Weighted combination of factors
        tis_score = (
            buffer_factor * 0.30 +
            historical_factor * 0.35 +
            train_factor * 0.20 +
            time_factor * 0.15
        ) * 100  # Convert to 0-100 scale
        
        # Determine risk level
        risk_level = self._classify_risk(tis_score)
        
        # Generate recommendation
        recommendation = self._generate_recommendation(
            risk_level, connection_time_minutes, transfer_station
        )
        
        transfer_score = TransferScore(
            transfer_station=transfer_station,
            arrival_train=arrival_train,
            departure_train=departure_train,
            connection_time_minutes=connection_time_minutes,
            tis_score=tis_score,
            risk_level=risk_level,
            historical_success_rate=historical_factor,
            factors={
                "buffer_score": buffer_factor,
                "historical_score": historical_factor,
                "train_score": train_factor,
                "time_score": time_factor
            },
            recommendation=recommendation
        )
        
        # Cache the result
        self._cache[cache_key] = transfer_score
        
        return transfer_score
    
    async def score_journey(
        self,
        journey: Journey,
        travel_date: Optional[str] = None
    ) -> JourneyTransferScore:
        """
        Calculate overall TIS for a complete journey with multiple transfers.
        
        Args:
            journey: Complete journey with all segments
            travel_date: Optional travel date
            
        Returns:
            JourneyTransferScore with overall assessment
        """
        if len(journey.segments) <= 1:
            # No transfers needed
            return JourneyTransferScore(
                journey=journey,
                overall_score=100.0,
                risk_level=RiskLevel.LOW,
                transfer_details=[],
                recommendations=["Direct route - no transfers required"],
                timestamp=datetime.utcnow()
            )
        
        transfer_scores = []
        
        # Score each transfer point
        for i in range(len(journey.segments) - 1):
            arrival_segment = journey.segments[i]
            departure_segment = journey.segments[i + 1]
            
            # Calculate connection time
            arrival_time = arrival_segment.arrival_time
            departure_time = departure_segment.departure_time
            
            if arrival_time and departure_time:
                # Calculate minutes between arrival and departure
                if hasattr(arrival_time, 'hour') and hasattr(departure_time, 'hour'):
                    arrival_minutes = arrival_time.hour * 60 + arrival_time.minute
                    departure_minutes = departure_time.hour * 60 + departure_time.minute
                    
                    # Handle day wrap-around (simple case)
                    if departure_minutes < arrival_minutes:
                        departure_minutes += 24 * 60
                    
                    connection_time = departure_minutes - arrival_minutes
                else:
                    connection_time = 30  # Default
            else:
                connection_time = 30  # Default
            
            transfer_score = await self.calculate_transfer_score(
                transfer_station=arrival_segment.to_station,
                arrival_train=arrival_segment.train_number,
                departure_train=departure_segment.train_number,
                connection_time_minutes=connection_time,
                travel_date=travel_date
            )
            
            transfer_scores.append(transfer_score)
        
        # Calculate overall score (weighted by connection time importance)
        if transfer_scores:
            # Weight by connection time (shorter connections are more critical)
            total_weight = sum(
                1.0 / (ts.connection_time_minutes + 1) 
                for ts in transfer_scores
            )
            weighted_score = sum(
                ts.tis_score * (1.0 / (ts.connection_time_minutes + 1))
                for ts in transfer_scores
            ) / total_weight if total_weight > 0 else 100.0
            
            overall_score = weighted_score
            worst_risk = max(ts.risk_level for ts in transfer_scores)
        else:
            overall_score = 100.0
            worst_risk = RiskLevel.LOW
        
        # Generate recommendations
        recommendations = self._generate_journey_recommendations(
            journey, transfer_scores
        )
        
        return JourneyTransferScore(
            journey=journey,
            overall_score=overall_score,
            risk_level=worst_risk,
            transfer_details=transfer_scores,
            recommendations=recommendations,
            timestamp=datetime.utcnow()
        )
    
    def _calculate_buffer_factor(
        self,
        station: str,
        connection_time: int
    ) -> float:
        """
        Calculate score based on buffer time vs required buffer.
        
        Higher score when connection time exceeds station's buffer requirement.
        """
        required_buffer = self.STATION_BUFFER_REQUIREMENTS.get(
            station, self.DEFAULT_BUFFER
        )
        
        if connection_time >= required_buffer:
            # Good buffer - score based on excess time
            excess = connection_time - required_buffer
            return min(1.0, 0.7 + (excess / 60))  # Cap at 1.0
        else:
            # Insufficient buffer - score drops quickly
            deficit = required_buffer - connection_time
            return max(0.0, 0.7 - (deficit / 30))
    
    def _calculate_historical_factor(
        self,
        station: str,
        arrival_train: str,
        departure_train: str
    ) -> float:
        """
        Calculate score based on historical connection success rate.
        """
        # Check known corridor success rates
        corridor_key = (station, station)  # Simplified
        return self.CONNECTION_SUCCESS_RATES.get(
            corridor_key, 0.70  # Default 70% if unknown
        )
    
    def _calculate_train_factor(
        self,
        arrival_train: str,
        departure_train: str
    ) -> float:
        """
        Calculate score based on train characteristics.
        
        Factors:
        - Train type (Rajdhani, Shatabdi have better on-time performance)
        - Train priority
        """
        # Premium trains have better on-time performance
        premium_trains = ["12001", "12002", "12009", "12010", "12201", "12202"]
        
        arrival_score = 0.8
        departure_score = 0.8
        
        if arrival_train[:4] in premium_trains:
            arrival_score = 0.9
        if departure_train[:4] in premium_trains:
            departure_score = 0.9
        
        return (arrival_score + departure_score) / 2
    
    def _calculate_time_factor(
        self,
        connection_time: int
    ) -> float:
        """
        Calculate score based on connection time alone.
        
        Optimal connection time is 20-45 minutes.
        Too short = high risk, too long = inconvenience but safe.
        """
        if connection_time < 15:
            return 0.3 + (connection_time / 50)  # 0.3 to 0.6
        elif connection_time < 25:
            return 0.6 + ((connection_time - 15) / 100)  # 0.6 to 0.7
        elif connection_time < 45:
            return 0.9 - ((connection_time - 25) / 100)  # 0.9 to 0.7
        elif connection_time < 90:
            return 0.7 - ((connection_time - 45) / 150)  # 0.7 to 0.4
        else:
            return max(0.3, 0.4 - ((connection_time - 90) / 300))  # Decay slowly
    
    def _classify_risk(self, tis_score: float) -> RiskLevel:
        """Classify risk level based on TIS score."""
        if tis_score >= self.RISK_THRESHOLD_LOW * 100:
            return RiskLevel.LOW
        elif tis_score >= self.RISK_THRESHOLD_MEDIUM * 100:
            return RiskLevel.MEDIUM
        elif tis_score > 0:
            return RiskLevel.HIGH
        else:
            return RiskLevel.UNKNOWN
    
    def _generate_recommendation(
        self,
        risk_level: RiskLevel,
        connection_time: int,
        station: str
    ) -> str:
        """Generate human-readable recommendation for transfer."""
        if risk_level == RiskLevel.LOW:
            return f"✅ Good connection at {station} ({connection_time}min buffer)"
        elif risk_level == RiskLevel.MEDIUM:
            return f"⚠️ Moderate risk at {station} - consider earlier train"
        elif risk_level == RiskLevel.HIGH:
            return f"❌ High risk at {station} - allow more connection time"
        else:
            return f"❓ Unknown connection quality at {station}"
    
    def _generate_journey_recommendations(
        self,
        journey: Journey,
        transfer_scores: List[TransferScore]
    ) -> List[str]:
        """Generate recommendations for the entire journey."""
        recommendations = []
        
        # Check for high-risk transfers
        high_risk = [ts for ts in transfer_scores if ts.risk_level == RiskLevel.HIGH]
        if high_risk:
            stations = ", ".join(ts.transfer_station for ts in high_risk)
            recommendations.append(
                f"⚠️ High-risk transfers at: {stations}. "
                f"Consider alternative routes."
            )
        
        # Check for very short connections
        short_connections = [
            ts for ts in transfer_scores 
            if ts.connection_time_minutes < 20
        ]
        if short_connections:
            recommendations.append(
                "🕐 Very short connections detected. "
                "Allow extra time for potential delays."
            )
        
        # Check for optimal journey
        if not high_risk and not short_connections:
            recommendations.append(
                "✅ This journey has good transfer connections."
            )
        
        return recommendations
    
    def get_transfer_indicator(
        self,
        transfer_score: TransferScore
    ) -> Dict[str, Any]:
        """
        Get visual indicator data for UI display.
        
        Returns:
            Dictionary with color, icon, and label for UI components
        """
        indicators = {
            RiskLevel.LOW: {
                "color": "green",
                "icon": "✅",
                "label": "Good Connection",
                "bg_color": "#d4edda",
                "text_color": "#155724"
            },
            RiskLevel.MEDIUM: {
                "color": "yellow",
                "icon": "⚠️",
                "label": "Moderate Risk",
                "bg_color": "#fff3cd",
                "text_color": "#856404"
            },
            RiskLevel.HIGH: {
                "color": "red",
                "icon": "❌",
                "label": "High Risk",
                "bg_color": "#f8d7da",
                "text_color": "#721c24"
            },
            RiskLevel.UNKNOWN: {
                "color": "gray",
                "icon": "❓",
                "label": "Unknown",
                "bg_color": "#e2e3e5",
                "text_color": "#383d41"
            }
        }
        
        base_indicator = indicators[transfer_score.risk_level]
        
        return {
            **base_indicator,
            "score": transfer_score.tis_score,
            "connection_time": transfer_score.connection_time_minutes,
            "station": transfer_score.transfer_station,
            "recommendation": transfer_score.recommendation
        }


# FastAPI Router for TIS endpoints
from fastapi import APIRouter, HTTPException

tis_router = APIRouter(prefix="/routes/transfer", tags=["Transfer Intelligence"])


@tis_router.get("/score")
async def get_transfer_score(
    transfer_station: str,
    arrival_train: str,
    departure_train: str,
    connection_time: int,
    travel_date: Optional[str] = None
) -> Dict[str, Any]:
    """
    Get Transfer Intelligence Score for a specific transfer point.
    
    Query Parameters:
    - transfer_station: Station code for transfer
    - arrival_train: Train number arriving at station
    - departure_train: Train number departing from station
    - connection_time: Connection time in minutes
    - travel_date: Optional travel date (YYYY-MM-DD)
    
    Returns:
    - TIS score (0-100)
    - Risk level (low/medium/high)
    - Visual indicator data
    - Recommendation
    """
    tis_service = TransferIntelligenceService()
    
    score = await tis_service.calculate_transfer_score(
        transfer_station=transfer_station,
        arrival_train=arrival_train,
        departure_train=departure_train,
        connection_time_minutes=connection_time,
        travel_date=travel_date
    )
    
    indicator = tis_service.get_transfer_indicator(score)
    
    return {
        "transfer_station": transfer_station,
        "arrival_train": arrival_train,
        "departure_train": departure_train,
        "connection_time_minutes": connection_time,
        "tis_score": score.tis_score,
        "risk_level": score.risk_level.value,
        "historical_success_rate": score.historical_success_rate,
        "factors": score.factors,
        "recommendation": score.recommendation,
        "indicator": indicator
    }


@tis_router.post("/score-journey")
async def score_journey_routes(
    journeys: List[Dict[str, Any]]
) -> List[Dict[str, Any]]:
    """
    Score multiple journeys by their transfer intelligence.
    
    Request Body:
    - List of journey objects with segments
    
    Returns:
    - List of scored journeys with TIS data
    """
    tis_service = TransferIntelligenceService()
    route_engine = RouteEngine()
    
    results = []
    
    for journey_data in journeys:
        try:
            # Reconstruct journey from data
            # This is simplified - actual implementation would use proper deserialization
            journey = Journey(
                segments=[
                    RouteSegment(
                        train_number=seg.get("train_number", ""),
                        train_name=seg.get("train_name", ""),
                        from_station=seg.get("from_station", ""),
                        to_station=seg.get("to_station", ""),
                        departure_time=seg.get("departure_time"),
                        arrival_time=seg.get("arrival_time"),
                        duration_minutes=seg.get("duration_minutes", 0),
                        available_classes=seg.get("classes", [])
                    )
                    for seg in journey_data.get("segments", [])
                ]
            )
            
            scored = await tis_service.score_journey(journey)
            
            results.append({
                "journey_id": journey_data.get("id", ""),
                "overall_score": scored.overall_score,
                "risk_level": scored.risk_level.value,
                "transfer_count": len(scored.transfer_details),
                "transfer_details": [
                    {
                        "station": ts.transfer_station,
                        "score": ts.tis_score,
                        "risk": ts.risk_level.value,
                        "connection_time": ts.connection_time_minutes,
                        "recommendation": ts.recommendation
                    }
                    for ts in scored.transfer_details
                ],
                "recommendations": scored.recommendations,
                "indicator": tis_service.get_transfer_indicator(
                    scored.transfer_details[0] if scored.transfer_details else None
                ) if scored.transfer_details else None
            })
            
        except Exception as e:
            logger.error(f"Error scoring journey: {e}")
            results.append({
                "error": str(e),
                "journey_id": journey_data.get("id", "unknown")
            })
    
    return results


@tis_router.get("/risk-summary")
async def get_corridor_risk_summary(
    source: str,
    destination: str
) -> Dict[str, Any]:
    """
    Get risk summary for all transfers between source and destination.
    
    Query Parameters:
    - source: Source station code
    - destination: Destination station code
    
    Returns:
    - Summary of transfer risks for the corridor
    """
    tis_service = TransferIntelligenceService()
    
    # Get common transfer stations for this corridor
    common_transfers = ["NDLS", "BCT", "MAS", "BLR", "CNB"]
    relevant_transfers = [
        station for station in common_transfers
        if station != source and station != destination
    ]
    
    transfer_risks = []
    for station in relevant_transfers[:3]:  # Top 3 transfer options
        score = await tis_service.calculate_transfer_score(
            transfer_station=station,
            arrival_train="",  # Would be filled based on actual trains
            departure_train="",
            connection_time_minutes=20
        )
        transfer_risks.append({
            "station": station,
            "risk_level": score.risk_level.value,
            "score": score.tis_score
        })
    
    return {
        "source": source,
        "destination": destination,
        "transfer_options": transfer_risks,
        "overall_assessment": "Multiple transfer options available with varying risk levels"
    }