"""
SOS Safety Service - Safety features and emergency response.
Implements safety index, emergency alerts, and location sharing.
"""

import uuid
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict, Any, Tuple
from dataclasses import dataclass, field
from enum import Enum

from sqlalchemy.orm import Session
from sqlalchemy import select

from database.models import SafetyIncident, UserEmergencyContact, SafetyAlert
from schemas.safety import (
    SOSRequest, SafetyAlertRequest, 
    EmergencyContact, SafetyScore
)

logger = logging.getLogger("sos_service")


class SafetyLevel(Enum):
    """Safety level classification."""
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


@dataclass
class SafetyScoreData:
    """Complete safety score breakdown."""
    overall_score: int
    station_score: int
    coach_score: int
    route_score: int
    time_score: int
    factors: List[str] = field(default_factory=list)
    recommendations: List[str] = field(default_factory=list)


class SOSService:
    """SOS and safety management service."""
    
    def __init__(self, db: Session):
        self.db = db
        self.active_sos = {}  # In production, use Redis for distributed state
    
    async def trigger_sos(
        self,
        user_id: str,
        booking_id: str,
        location: Optional[Dict[str, float]] = None,
        description: Optional[str] = None,
        is_test: bool = False
    ) -> Dict[str, Any]:
        """
        Trigger SOS emergency alert.
        
        Args:
            user_id: User triggering SOS
            booking_id: Related booking ID
            location: Optional GPS coordinates {lat, lng}
            description: Optional SOS description
            is_test: If True, prevents actual notifications
            
        Returns:
            SOS confirmation with emergency contacts
        """
        sos_id = str(uuid.uuid4())
        
        # Create safety incident record
        incident = SafetyIncident(
            id=sos_id,
            user_id=user_id,
            booking_id=booking_id,
            incident_type="sos_triggered",
            status="active",
            location=location,
            description=description or "SOS triggered by user",
            created_at=datetime.now(timezone.utc)
        )
        
        self.db.add(incident)
        
        # Get emergency contacts
        contacts = await self._get_emergency_contacts(user_id)
        
        # Send alerts to contacts
        alert_results = []
        if not is_test:
            for contact in contacts:
                alert = await self._send_emergency_alert(contact, incident, location)
                alert_results.append(alert)
        
        safety_score = await self._get_safety_score(booking_id)
        
        # Track active SOS

        self.active_sos[sos_id] = {
            "user_id": user_id,
            "booking_id": booking_id,
            "started_at": datetime.now(timezone.utc),
            "location": location
        }
        
        self.db.commit()
        
        return {
            "sos_id": sos_id,
            "status": "active",
            "emergency_contacts_notified": len(contacts),
            "alerts_sent": alert_results,
            "safety_score": safety_score.overall_score,
            "recommendations": safety_score.recommendations
        }
    
    async def resolve_sos(
        self,
        sos_id: str,
        user_id: str,
        resolution: str = "resolved"
    ) -> Dict[str, Any]:
        """Resolve an active SOS."""
        if sos_id not in self.active_sos:
            raise ValueError(f"SOS {sos_id} not found or already resolved")
        
        incident = self.db.get(SafetyIncident, sos_id)
        if not incident:
            raise ValueError(f"Incident {sos_id} not found")
        
        # Update incident
        incident.status = resolution
        incident.resolved_at = datetime.now(timezone.utc)
        incident.resolution_notes = resolution
        
        # Remove from active SOS
        self.active_sos.pop(sos_id, None)
        
        self.db.commit()
        
        return {
            "sos_id": sos_id,
            "status": resolution,
            "resolved_at": datetime.now(timezone.utc).isoformat()
        }
    
    async def get_safety_score(
        self,
        booking_id: str
    ) -> SafetyScoreData:
        """
        Calculate comprehensive safety score for a booking.
        
        Factors:
        - Station safety ratings
        - Coach security features
        - Route safety history
        - Time of day
        - Historical incident data
        """
        # In production, this would query real safety data
        # For now, implement the scoring logic
        
        try:
            from database.models import Booking
            booking = self.db.get(Booking, booking_id)
            
            if not booking:
                return SafetyScoreData(
                    overall_score=0,
                    station_score=0,
                    coach_score=0,
                    route_score=0,
                    time_score=0,
                    factors=["Booking not found"],
                    recommendations=["Unable to calculate safety score"]
                )
            
            # Calculate individual scores
            station_score = await self._calculate_station_score(
                booking.from_station_code,
                booking.to_station_code
            )
            
            coach_score = await self._calculate_coach_score(
                booking.train_number,
                booking.class_type
            )
            
            route_score = await self._calculate_route_score(
                booking.from_station_code,
                booking.to_station_code
            )
            
            time_score = self._calculate_time_score(booking.travel_date)
            
            # Calculate overall score (weighted average)
            overall = int(
                station_score * 0.25 +
                coach_score * 0.30 +
                route_score * 0.25 +
                time_score * 0.20
            )
            
            # Generate factors and recommendations
            factors = []
            recommendations = []
            
            if station_score < 70:
                factors.append(f"Station safety rating: {station_score}/100")
                recommendations.append("Exercise caution at stations, especially late at night")
            
            if coach_score < 70:
                factors.append(f"Coach security features: {coach_score}/100")
                recommendations.append("Stay in coach with CCTV coverage if available")
            
            if route_score < 70:
                factors.append(f"Route safety history: {route_score}/100")
                recommendations.append("Be aware of high-incident areas on this route")
            
            if time_score < 70:
                factors.append(f"Travel time safety: {time_score}/100")
                recommendations.append("Night travel requires extra precautions")
            
            return SafetyScoreData(
                overall_score=overall,
                station_score=station_score,
                coach_score=coach_score,
                route_score=route_score,
                time_score=time_score,
                factors=factors,
                recommendations=recommendations
            )
            
        except Exception as e:
            logger.error(f"Error calculating safety score: {e}")
            return SafetyScoreData(
                overall_score=50,
                station_score=50,
                coach_score=50,
                route_score=50,
                time_score=50,
                factors=["Error calculating safety data"],
                recommendations=["Contact support for safety information"]
            )
    
    async def _calculate_station_score(
        self,
        from_station: str,
        to_station: str
    ) -> int:
        """Calculate station safety score."""
        # In production, query real safety ratings
        # Mock implementation
        station_ratings = {
            "NDLS": 95,  # New Delhi
            "BCT": 90,   # Mumbai
            "MAS": 92,   # Chennai
            "HWH": 88,   # Howrah
            "SC": 85,    # Secunderabad
            "LKO": 82,   # Lucknow
            "JP": 78,    # Jaipur
            "DHN": 75,   # Dhanbad
        }
        
        from_rating = station_ratings.get(from_station, 70)
        to_rating = station_ratings.get(to_station, 70)
        
        return min(from_rating, to_rating)
    
    async def _calculate_coach_score(
        self,
        train_number: str,
        class_type: str
    ) -> int:
        """Calculate coach safety score."""
        # AC coaches generally have better security features
        coach_scores = {
            "1A": 95,  # First AC - best security
            "2A": 90,  # AC 2-Tier
            "3A": 85,  # AC 3-Tier
            "CC": 80,  # AC Chair Car
            "EC": 88,  # Executive Chair
            "SL": 70,  # Sleeper - basic
            "2S": 65,  # Second Seating
        }
        
        base_score = coach_scores.get(class_type, 70)
        
        # Add some variance based on train
        train_factor = hash(train_number) % 10
        return min(100, base_score + train_factor)
    
    async def _calculate_route_score(
        self,
        from_station: str,
        to_station: str
    ) -> int:
        """Calculate route safety score based on historical data."""
        # In production, query incident database
        # Mock implementation
        high_risk_routes = [
            ("DHN", "BCT"),  # Example high-risk route
        ]
        
        route = (from_station, to_station)
        reverse_route = (to_station, from_station)
        
        if route in high_risk_routes or reverse_route in high_risk_routes:
            return 55
        
        # Most routes are moderate to high safety
        return 80
    
    def _calculate_time_score(self, travel_date) -> int:
        """Calculate safety score based on time of day."""
        # Night travel (10 PM - 6 AM) is lower safety
        return 85  # Simplified for MVP
    
    async def _get_emergency_contacts(
        self,
        user_id: str
    ) -> List[EmergencyContact]:
        """Get user's emergency contacts."""
        result = self.db.execute(
            select(UserEmergencyContact).where(
                UserEmergencyContact.user_id == user_id,
                UserEmergencyContact.is_active == True
            )
        ).scalars().all()
        
        return [
            EmergencyContact(
                id=str(contact.id),
                name=contact.name,
                phone=contact.phone,
                relationship=contact.relationship,
                priority=contact.priority
            )
            for contact in result
        ]
    
    async def _send_emergency_alert(
        self,
        contact: EmergencyContact,
        incident: SafetyIncident,
        location: Optional[Dict[str, float]]
    ) -> Dict[str, Any]:
        """Send emergency alert to contact."""
        # In production, integrate with SMS/notification service
        message = (
            f"🚨 EMERGENCY ALERT\n\n"
            f"Your contact {contact.name} has triggered an SOS.\n"
            f"Time: {incident.created_at.strftime('%Y-%m-%d %H:%M:%S')}\n"
        )
        
        if location:
            message += f"Location: https://maps.google.com/?q={location['lat']},{location['lng']}\n"
        
        message += f"\nBooking ID: {incident.booking_id}\n"
        message += f"Description: {incident.description}\n\n"
        message += "Please contact emergency services if needed: 112"
        
        # Log for now - in production, send actual notification
        logger.info(f"Emergency alert sent to {contact.phone}: {message[:100]}...")
        
        return {
            "contact_id": contact.id,
            "contact_name": contact.name,
            "phone": contact.phone,
            "status": "sent",
            "timestamp": datetime.now(timezone.utc).isoformat()
        }
    
    async def _notify_emergency_services(
        self,
        incident: SafetyIncident,
        location: Optional[Dict[str, float]]
    ) -> None:
        """Notify official emergency services."""
        # In production, integrate with police/Railway Protection Force
        logger.warning(
            f"EMERGENCY SERVICES NOTIFICATION - SOS: {incident.id}, "
            f"Location: {location}, Booking: {incident.booking_id}"
        )
    
    async def report_safety_incident(
        self,
        user_id: str,
        booking_id: str,
        incident_type: str,
        description: str,
        location: Optional[Dict[str, float]] = None,
        evidence: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """Report a safety incident."""
        incident_id = str(uuid.uuid4())
        
        incident = SafetyIncident(
            id=incident_id,
            user_id=user_id,
            booking_id=booking_id,
            incident_type=incident_type,
            description=description,
            location=location,
            evidence=evidence,
            status="reported",
            created_at=datetime.now(timezone.utc)
        )
        
        self.db.add(incident)
        self.db.commit()
        
        return {
            "incident_id": incident_id,
            "status": "reported",
            "message": "Thank you for reporting. We take your safety seriously."
        }
    
    async def get_safety_alerts(
        self,
        station_code: Optional[str] = None,
        route: Optional[Tuple[str, str]] = None
    ) -> List[Dict[str, Any]]:
        """Get active safety alerts for a station or route."""
        query = select(SafetyAlert).where(
            SafetyAlert.is_active == True,
            SafetyAlert.expires_at > datetime.now(timezone.utc)
        )
        
        if station_code:
            query = query.where(
                (SafetyAlert.station_code == station_code) |
                (SafetyAlert.affected_stations.contains([station_code]))
            )
        
        if route:
            query = query.where(
                (SafetyAlert.route_from == route[0]) |
                (SafetyAlert.route_to == route[1])
            )
        
        result = self.db.execute(query).scalars().all()
        
        return [
            {
                "alert_id": alert.id,
                "type": alert.alert_type,
                "severity": alert.severity,
                "message": alert.message,
                "station": alert.station_code,
                "expires_at": alert.expires_at.isoformat()
            }
            for alert in result
        ]
    
    async def add_emergency_contact(
        self,
        user_id: str,
        name: str,
        phone: str,
        relationship: str,
        priority: int = 1
    ) -> EmergencyContact:
        """Add emergency contact for user."""
        contact = UserEmergencyContact(
            id=str(uuid.uuid4()),
            user_id=user_id,
            name=name,
            phone=phone,
            relationship=relationship,
            priority=priority,
            is_active=True,
            created_at=datetime.now(timezone.utc)
        )
        
        self.db.add(contact)
        self.db.commit()
        
        return EmergencyContact(
            id=contact.id,
            name=contact.name,
            phone=contact.phone,
            relationship=contact.relationship,
            priority=contact.priority
        )
    
    async def get_active_sos_count(self) -> int:
        """Get count of active SOS incidents."""
        return len(self.active_sos)


# Singleton instance
sos_service = None

def get_sos_service(db: Session) -> SOSService:
    """Get or create SOS service instance."""
    global sos_service
    if sos_service is None:
        sos_service = SOSService(db)
    return sos_service