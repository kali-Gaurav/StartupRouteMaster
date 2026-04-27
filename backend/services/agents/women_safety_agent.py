"""
Women Safety Agent
=================
Handles women-specific safety features and risk assessment
"""
import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from services.agents.base_agent import BaseAgent

logger = logging.getLogger("agent.women_safety")

class WomenSafetyAgent(BaseAgent):
    """Handles women-specific safety features"""
    
    name = "WomenSafetyAgent"
    description = "Manages women-specific safety features, risk assessment, and route safety scoring"
    category = "safety"
    icon = "👩‍🦰"
    color = "#FF6B6B"
    
    def __init__(self):
        super().__init__()
        self.safety_scores_cache = {}
    
    async def on_start(self):
        """Initialize women safety agent"""
        logger.info("👩‍🦰 WomenSafetyAgent starting...")
        # Load safety data
        await self.load_safety_data()
        return True
    
    async def load_safety_data(self):
        """Load women safety data"""
        try:
            # Load station safety scores
            from database.session import SessionTransit
            from sqlalchemy import text
            
            db = SessionTransit()
            try:
                result = db.execute(text("""
                    SELECT station_code, women_safety_score, lighting_score, crowd_density_score 
                    FROM station_safety_scores 
                    WHERE women_safety_score IS NOT NULL
                """))
                
                for row in result:
                    station_code = row[0]
                    self.safety_scores_cache[station_code] = {
                        "women_safety_score": row[1] or 0.5,
                        "lighting_score": row[2] or 0.5,
                        "crowd_density_score": row[3] or 0.5
                    }
                
                logger.info(f"Loaded safety scores for {len(self.safety_scores_cache)} stations")
            finally:
                db.close()
                
        except Exception as e:
            logger.warning(f"⚠️ Could not load safety data: {e}")
            # Use default safety scores
            self.safety_scores_cache = {}
    
    async def assess_route_safety(self, route_details: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Assess safety of a route for women travelers"""
        try:
            stations = route_details.get("stations", [])
            segments = route_details.get("segments", [])
            travel_time = route_details.get("travel_time")
            
            # Calculate safety scores
            station_scores = []
            total_score = 0
            station_count = 0
            
            for station in stations:
                station_code = station.get("code")
                if station_code:
                    score = self.get_station_safety_score(station_code)
                    station_scores.append({
                        "station": station_code,
                        "safety_score": score,
                        "details": self.safety_scores_cache.get(station_code, {})
                    })
                    total_score += score
                    station_count += 1
            
            # Time-based risk assessment
            time_risk = self.assess_time_risk(travel_time)
            
            # Segment risk assessment
            segment_risks = []
            for segment in segments:
                segment_risk = self.assess_segment_risk(segment)
                segment_risks.append(segment_risk)
            
            # Overall safety rating
            avg_station_score = total_score / max(station_count, 1)
            overall_safety = self.calculate_overall_safety(avg_station_score, time_risk, segment_risks)
            
            # Recommendations
            recommendations = self.generate_safety_recommendations(
                overall_safety, 
                station_scores, 
                time_risk,
                route_details
            )
            
            return {
                "operation": "route_safety_assessment",
                "status": "completed",
                "overall_safety_score": overall_safety["score"],
                "safety_level": overall_safety["level"],
                "station_scores": station_scores,
                "time_risk": time_risk,
                "segment_risks": segment_risks,
                "recommendations": recommendations,
                "women_specific_advice": self.get_women_specific_advice(overall_safety["level"])
            }
            
        except Exception as e:
            logger.error(f"❌ Route safety assessment failed: {e}")
            return {
                "operation": "route_safety_assessment",
                "status": "failed",
                "error": str(e)
            }
    
    def get_station_safety_score(self, station_code: str) -> float:
        """Get safety score for a station (0-1, higher is safer)"""
        if station_code in self.safety_scores_cache:
            scores = self.safety_scores_cache[station_code]
            # Weighted average
            return (
                scores.get("women_safety_score", 0.5) * 0.5 +
                scores.get("lighting_score", 0.5) * 0.3 +
                scores.get("crowd_density_score", 0.5) * 0.2
            )
        return 0.5  # Default score
    
    def assess_time_risk(self, travel_time: Optional[str]) -> Dict[str, Any]:
        """Assess risk based on time of travel"""
        now = datetime.now()
        hour = now.hour
        
        if travel_time:
            # Parse travel time if provided
            try:
                travel_hour = int(travel_time.split(":")[0])
                hour = travel_hour
            except:
                pass
        
        # Night time is higher risk
        if 22 <= hour <= 5 or hour < 5:  # 10 PM to 5 AM
            risk_level = "high"
            risk_score = 0.3
        elif 18 <= hour <= 21:  # 6 PM to 9 PM
            risk_level = "medium"
            risk_score = 0.6
        else:  # Daytime
            risk_level = "low"
            risk_score = 0.8
        
        return {
            "risk_level": risk_level,
            "risk_score": risk_score,
            "hour": hour,
            "advice": self.get_time_based_advice(risk_level)
        }
    
    def assess_segment_risk(self, segment: Dict[str, Any]) -> Dict[str, Any]:
        """Assess risk for a travel segment"""
        # Simplified risk assessment
        # In production, would consider:
        # - Train type (Express vs Local)
        # - Coach type (AC vs Sleeper)
        # - Duration
        # - Historical incident data
        
        duration_minutes = segment.get("duration_minutes", 0)
        train_type = segment.get("train_type", "unknown")
        coach_type = segment.get("coach_type", "unknown")
        
        # Base risk
        risk_score = 0.7
        
        # Adjust based on factors
        if duration_minutes > 300:  # > 5 hours
            risk_score *= 0.9  # Slightly higher risk
        
        if train_type.lower() == "local":
            risk_score *= 0.8  # Local trains higher risk
        
        if coach_type.lower() in ["ac1", "ac2", "ac3"]:
            risk_score *= 1.1  # AC coaches slightly safer
        
        return {
            "segment_id": segment.get("id"),
            "duration_minutes": duration_minutes,
            "train_type": train_type,
            "coach_type": coach_type,
            "risk_score": min(max(risk_score, 0.1), 1.0),
            "risk_level": "high" if risk_score < 0.4 else "medium" if risk_score < 0.7 else "low"
        }
    
    def calculate_overall_safety(self, avg_station_score: float, 
                               time_risk: Dict[str, Any], 
                               segment_risks: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Calculate overall safety score"""
        # Weighted average
        time_score = time_risk.get("risk_score", 0.5)
        
        avg_segment_score = 0.5
        if segment_risks:
            avg_segment_score = sum(s["risk_score"] for s in segment_risks) / len(segment_risks)
        
        overall_score = (
            avg_station_score * 0.4 +
            time_score * 0.3 +
            avg_segment_score * 0.3
        )
        
        # Determine safety level
        if overall_score >= 0.7:
            level = "safe"
            color = "green"
        elif overall_score >= 0.5:
            level = "moderate"
            color = "yellow"
        elif overall_score >= 0.3:
            level = "risky"
            color = "orange"
        else:
            level = "dangerous"
            color = "red"
        
        return {
            "score": round(overall_score, 2),
            "level": level,
            "color": color,
            "description": self.get_safety_description(level)
        }
    
    def generate_safety_recommendations(self, overall_safety: Dict[str, Any],
                                      station_scores: List[Dict[str, Any]],
                                      time_risk: Dict[str, Any],
                                      route_details: Dict[str, Any]) -> List[str]:
        """Generate safety recommendations"""
        recommendations = []
        
        # Overall safety recommendation
        if overall_safety["level"] in ["risky", "dangerous"]:
            recommendations.append("⚠️ Consider traveling with a companion or using our Sathi service")
        
        # Time-based recommendations
        if time_risk["risk_level"] == "high":
            recommendations.append("🌙 Night travel detected - Enable Safety Shield for real-time monitoring")
        
        # Station-specific recommendations
        risky_stations = [s for s in station_scores if s["safety_score"] < 0.4]
        if risky_stations:
            station_names = ", ".join([s["station"] for s in risky_stations[:3]])
            recommendations.append(f"🚨 Be cautious at stations: {station_names}")
        
        # General women safety tips
        recommendations.extend([
            "📱 Keep your phone charged and location sharing enabled",
            "👥 Share your journey details with trusted contacts",
            "🚨 Know the location of women's compartments and RPF posts",
            "⏰ Arrive at stations well before departure time"
        ])
        
        return recommendations
    
    def get_women_specific_advice(self, safety_level: str) -> List[str]:
        """Get women-specific safety advice"""
        advice = {
            "safe": [
                "Route is generally safe for women travelers",
                "Standard precautions recommended"
            ],
            "moderate": [
                "Exercise standard caution",
                "Consider traveling during daylight hours",
                "Use well-lit areas of stations"
            ],
            "risky": [
                "⚠️ Strongly recommend traveling with companion",
                "Enable real-time location sharing",
                "Avoid isolated areas of stations",
                "Consider using women-only coach if available"
            ],
            "dangerous": [
                "🚨 NOT RECOMMENDED for solo women travelers",
                "Mandatory: Travel with trusted companion",
                "Enable Safety Shield with 5-minute check-ins",
                "Pre-book Sathi guide for entire journey",
                "Have emergency contacts on speed dial"
            ]
        }
        
        return advice.get(safety_level, advice["moderate"])
    
    def get_time_based_advice(self, risk_level: str) -> str:
        """Get time-based safety advice"""
        advice = {
            "low": "Daytime travel - standard precautions",
            "medium": "Evening travel - increased vigilance recommended",
            "high": "Night travel - enhanced safety measures required"
        }
        return advice.get(risk_level, "Standard precautions")
    
    def get_safety_description(self, level: str) -> str:
        """Get safety level description"""
        descriptions = {
            "safe": "Generally safe for women travelers",
            "moderate": "Moderate risk - standard precautions advised",
            "risky": "Higher risk - enhanced safety measures recommended",
            "dangerous": "High risk - avoid solo travel if possible"
        }
        return descriptions.get(level, "Risk assessment unavailable")
    
    async def find_female_sathis(self, station_code: str, **kwargs) -> Dict[str, Any]:
        """Find female Sathis available at a station"""
        try:
            from database.session import get_db
            from database.models import Sathi
            from sqlalchemy import func
            
            db = next(get_db())
            
            from sqlalchemy.dialects.postgresql import JSONB
            
            # Query for female Sathis
            sathis = db.query(Sathi).filter(
                Sathi.is_available == True,
                Sathi.verification_status == "active",
                Sathi.gender == "female",
                Sathi.service_stations.cast(JSONB).contains([station_code])
            ).limit(10).all()
            
            result = []
            for sathi in sathis:
                result.append({
                    "id": sathi.id,
                    "name": sathi.full_name,
                    "rating": sathi.rating,
                    "languages": sathi.languages_spoken,
                    "specializations": sathi.specializations,
                    "has_first_aid": sathi.has_first_aid_certification,
                    "hourly_rate": sathi.hourly_rate
                })
            
            return {
                "operation": "find_female_sathis",
                "status": "completed",
                "station_code": station_code,
                "count": len(result),
                "sathis": result,
                "message": f"Found {len(result)} female Sathis at {station_code}"
            }
            
        except Exception as e:
            logger.error(f"❌ Find female Sathis failed: {e}")
            return {
                "operation": "find_female_sathis",
                "status": "failed",
                "error": str(e)
            }
    
    async def execute(self, task: str, **kwargs) -> Dict[str, Any]:
        """Execute women safety task"""
        task_lower = task.lower()
        
        if "assess" in task_lower or "safety" in task_lower:
            if "route" in task_lower:
                route_details = kwargs.get("route_details", {})
                return await self.assess_route_safety(route_details, **kwargs)
            else:
                return {
                    "operation": "safety_assessment",
                    "status": "failed",
                    "error": "Please provide route_details for assessment"
                }
        
        elif "female" in task_lower or "sathi" in task_lower:
            station_code = kwargs.get("station_code", "")
            if station_code:
                return await self.find_female_sathis(station_code, **kwargs)
            else:
                return {
                    "operation": "find_female_sathis",
                    "status": "failed",
                    "error": "Please provide station_code"
                }
        
        elif "recommend" in task_lower or "advice" in task_lower:
            safety_level = kwargs.get("safety_level", "moderate")
            return {
                "operation": "safety_recommendations",
                "status": "completed",
                "safety_level": safety_level,
                "recommendations": self.get_women_specific_advice(safety_level),
                "general_advice": [
                    "Always trust your instincts",
                    "Keep emergency numbers saved",
                    "Use well-lit and populated areas",
                    "Share live location with trusted contacts"
                ]
            }
        
        else:
            return {
                "operation": "unknown",
                "status": "failed",
                "error": f"Unknown women safety task: {task}"
            }