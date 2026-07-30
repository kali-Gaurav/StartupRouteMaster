"""
Family Safety Agent
==================
Handles family group safety features and coordination
"""
import logging
import asyncio
from typing import Dict, Any, List, Optional
from datetime import datetime, timedelta
from services.agents.base_agent import BaseAgent

logger = logging.getLogger("agent.family_safety")

class FamilySafetyAgent(BaseAgent):
    """Handles family group safety and coordination"""
    
    name = "FamilySafetyAgent"
    description = "Manages family group safety features, member tracking, and group coordination"
    category = "family"
    icon = "👨‍👩‍👧‍👦"
    color = "#4ECDC4"
    
    def __init__(self):
        super().__init__()
        self.family_groups_cache = {}
    
    async def on_start(self):
        """Initialize family safety agent"""
        logger.info("👨‍👩‍👧‍👦 FamilySafetyAgent starting...")
        return True
    
    async def create_family_group(self, group_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Create a new family group"""
        try:
            from database.session import get_db
            from database.models import FamilyGroup, User
            
            db = next(get_db())
            
            # Validate owner
            owner_id = group_data.get("owner_id")
            if not owner_id:
                return {
                    "operation": "create_family_group",
                    "status": "failed",
                    "error": "Owner ID is required"
                }
            
            # Create family group
            family_group = FamilyGroup(
                owner_id=owner_id,
                group_name=group_data.get("group_name", "My Family"),
                members=[owner_id],
                notification_preferences=group_data.get("notification_preferences", {
                    "sos_alerts": True,
                    "journey_updates": True,
                    "checkpoint_alerts": True,
                    "delay_alerts": True,
                    "sathi_assignment": True
                }),
                auto_share_location=group_data.get("auto_share_location", True),
                require_check_ins=group_data.get("require_check_ins", True),
                check_in_interval_minutes=group_data.get("check_in_interval_minutes", 30)
            )
            
            db.add(family_group)
            db.commit()
            db.refresh(family_group)
            
            # Cache the group
            self.family_groups_cache[family_group.id] = {
                "id": family_group.id,
                "name": family_group.group_name,
                "owner": owner_id,
                "members": [owner_id],
                "created_at": datetime.utcnow()
            }
            
            logger.info(f"Family group created: {family_group.group_name} ({family_group.id})")
            
            return {
                "operation": "create_family_group",
                "status": "completed",
                "family_group_id": family_group.id,
                "group_name": family_group.group_name,
                "owner_id": owner_id,
                "members": [owner_id],
                "message": "Family group created successfully"
            }
            
        except Exception as e:
            logger.error(f"❌ Create family group failed: {e}")
            return {
                "operation": "create_family_group",
                "status": "failed",
                "error": str(e)
            }
    
    async def add_family_member(self, group_id: str, member_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Add member to family group"""
        try:
            from database.session import get_db
            from database.models import FamilyGroup
            
            db = next(get_db())
            
            # Get family group
            family_group = db.query(FamilyGroup).filter(FamilyGroup.id == group_id).first()
            if not family_group:
                return {
                    "operation": "add_family_member",
                    "status": "failed",
                    "error": "Family group not found"
                }
            
            # Add member
            member_id = member_data.get("user_id")
            if not member_id:
                return {
                    "operation": "add_family_member",
                    "status": "failed",
                    "error": "User ID is required"
                }
            
            # Check if already a member
            if member_id in family_group.members:
                return {
                    "operation": "add_family_member",
                    "status": "failed",
                    "error": "User is already a family member"
                }
            
            # Add to members list
            current_members = family_group.members or []
            current_members.append(member_id)
            family_group.members = current_members
            
            # Update member roles if provided
            member_roles = family_group.member_roles or {}
            member_roles[member_id] = member_data.get("role", "member")
            family_group.member_roles = member_roles
            
            db.commit()
            
            # Update cache
            if group_id in self.family_groups_cache:
                self.family_groups_cache[group_id]["members"].append(member_id)
            
            logger.info(f"Member {member_id} added to family group {group_id}")
            
            return {
                "operation": "add_family_member",
                "status": "completed",
                "family_group_id": group_id,
                "member_id": member_id,
                "total_members": len(family_group.members),
                "message": "Family member added successfully"
            }
            
        except Exception as e:
            logger.error(f"❌ Add family member failed: {e}")
            return {
                "operation": "add_family_member",
                "status": "failed",
                "error": str(e)
            }
    
    async def track_family_journey(self, journey_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Track family member journey"""
        try:
            from database.session import get_db
            from database.models import JourneyPlan, FamilyGroup
            
            db = next(get_db())
            
            passenger_id = journey_data.get("passenger_id")
            family_group_id = journey_data.get("family_group_id")
            
            if not passenger_id:
                return {
                    "operation": "track_family_journey",
                    "status": "failed",
                    "error": "Passenger ID is required"
                }
            
            # Create or update journey plan
            journey_plan = JourneyPlan(
                passenger_id=passenger_id,
                family_group_id=family_group_id,
                journey_type=journey_data.get("journey_type", "train"),
                start_station_code=journey_data.get("start_station_code"),
                end_station_code=journey_data.get("end_station_code"),
                planned_departure=journey_data.get("planned_departure"),
                planned_arrival=journey_data.get("planned_arrival"),
                route_details=journey_data.get("route_details", {}),
                pnr_numbers=journey_data.get("pnr_numbers", []),
                train_numbers=journey_data.get("train_numbers", []),
                safety_level=journey_data.get("safety_level", "standard"),
                requires_sathi=journey_data.get("requires_sathi", False),
                sathi_preferences=journey_data.get("sathi_preferences", {}),
                status="active"
            )
            
            db.add(journey_plan)
            db.commit()
            db.refresh(journey_plan)
            
            # Notify family members if group exists
            notification_count = 0
            if family_group_id:
                family_group = db.query(FamilyGroup).filter(FamilyGroup.id == family_group_id).first()
                if family_group:
                    members_to_notify = family_group.members or []
                    # Remove passenger from notification list
                    members_to_notify = [m for m in members_to_notify if m != passenger_id]
                    
                    notification_count = len(members_to_notify)
                    logger.info(f"Journey tracking started for {passenger_id}, notifying {notification_count} family members")
            
            return {
                "operation": "track_family_journey",
                "status": "completed",
                "journey_plan_id": journey_plan.id,
                "passenger_id": passenger_id,
                "family_notifications_sent": notification_count,
                "checkpoints": journey_plan.checkpoints or [],
                "message": "Family journey tracking started"
            }
            
        except Exception as e:
            logger.error(f"❌ Track family journey failed: {e}")
            return {
                "operation": "track_family_journey",
                "status": "failed",
                "error": str(e)
            }
    
    async def send_family_alert(self, alert_data: Dict[str, Any], **kwargs) -> Dict[str, Any]:
        """Send alert to family members"""
        try:
            from database.session import get_db
            from database.models import FamilyGroup
            
            db = next(get_db())
            
            group_id = alert_data.get("family_group_id")
            alert_type = alert_data.get("alert_type", "general")
            message = alert_data.get("message", "")
            urgency = alert_data.get("urgency", "medium")
            
            if not group_id:
                return {
                    "operation": "send_family_alert",
                    "status": "failed",
                    "error": "Family group ID is required"
                }
            
            # Get family group
            family_group = db.query(FamilyGroup).filter(FamilyGroup.id == group_id).first()
            if not family_group:
                return {
                    "operation": "send_family_alert",
                    "status": "failed",
                    "error": "Family group not found"
                }
            
            # Get members to notify
            members = family_group.members or []
            notification_preferences = family_group.notification_preferences or {}
            
            # Filter based on notification preferences
            members_to_notify = []
            for member_id in members:
                # Check if this alert type is enabled for member
                # (Simplified - in production would check per-member preferences)
                if notification_preferences.get(f"{alert_type}_alerts", True):
                    members_to_notify.append(member_id)
            
            # Send notifications (simulated)
            notification_results = []
            for member_id in members_to_notify:
                # In production: Send push notification, SMS, email, etc.
                notification_results.append({
                    "member_id": member_id,
                    "status": "sent",
                    "channel": "push",  # push, sms, email, whatsapp
                    "timestamp": datetime.utcnow().isoformat()
                })
            
            logger.info(f"Family alert sent to {len(notification_results)} members: {alert_type} - {message}")
            
            return {
                "operation": "send_family_alert",
                "status": "completed",
                "family_group_id": group_id,
                "alert_type": alert_type,
                "message": message,
                "urgency": urgency,
                "notifications_sent": len(notification_results),
                "notification_results": notification_results,
                "message": f"Family alert sent to {len(notification_results)} members"
            }
            
        except Exception as e:
            logger.error(f"❌ Send family alert failed: {e}")
            return {
                "operation": "send_family_alert",
                "status": "failed",
                "error": str(e)
            }
    
    async def get_family_dashboard(self, group_id: str, **kwargs) -> Dict[str, Any]:
        """Get family safety dashboard"""
        try:
            from database.session import get_db
            from database.models import FamilyGroup, JourneyPlan
            
            db = next(get_db())
            
            # Get family group
            family_group = db.query(FamilyGroup).filter(FamilyGroup.id == group_id).first()
            if not family_group:
                return {
                    "operation": "get_family_dashboard",
                    "status": "failed",
                    "error": "Family group not found"
                }
            
            # Get active journeys for family members
            active_journeys = []
            members = family_group.members or []
            
            for member_id in members:
                member_journeys = db.query(JourneyPlan).filter(
                    JourneyPlan.passenger_id == member_id,
                    JourneyPlan.status == "active"
                ).all()
                
                for journey in member_journeys:
                    active_journeys.append({
                        "journey_id": journey.id,
                        "passenger_id": journey.passenger_id,
                        "start_station": journey.start_station_code,
                        "end_station": journey.end_station_code,
                        "status": journey.status,
                        "next_checkpoint": journey.next_checkpoint_index,
                        "total_checkpoints": len(journey.checkpoints or []),
                        "requires_sathi": journey.requires_sathi,
                        "safety_level": journey.safety_level
                    })
            
            # Get family safety stats
            total_members = len(members)
            active_travelers = len(set(j["passenger_id"] for j in active_journeys))
            
            # Check for any SOS events (simplified)
            # In production: Query SOSEvent table
            
            return {
                "operation": "get_family_dashboard",
                "status": "completed",
                "family_group_id": group_id,
                "group_name": family_group.group_name,
                "owner_id": family_group.owner_id,
                "total_members": total_members,
                "active_travelers": active_travelers,
                "active_journeys": active_journeys,
                "safety_settings": {
                    "auto_share_location": family_group.auto_share_location,
                    "require_check_ins": family_group.require_check_ins,
                    "check_in_interval": family_group.check_in_interval_minutes
                },
                "notification_preferences": family_group.notification_preferences,
                "emergency_contacts": family_group.emergency_contacts or [],
                "last_updated": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"❌ Get family dashboard failed: {e}")
            return {
                "operation": "get_family_dashboard",
                "status": "failed",
                "error": str(e)
            }
    
    async def execute(self, context: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Execute family safety task"""
        context = context or {}
        task = str(context.get("task", "")).lower()
        
        if "create" in task and "family" in task:
            group_data = context.get("group_data", {})
            return await self.create_family_group(group_data, **context)
        
        elif "add" in task and "member" in task:
            group_id = context.get("group_id", "")
            member_data = context.get("member_data", {})
            if group_id:
                return await self.add_family_member(group_id, member_data, **context)
            else:
                return {
                    "operation": "add_family_member",
                    "status": "failed",
                    "error": "Group ID is required"
                }
        
        elif "track" in task and "journey" in task:
            journey_data = context.get("journey_data", {})
            return await self.track_family_journey(journey_data, **context)
        
        elif "alert" in task or "notify" in task:
            alert_data = context.get("alert_data", {})
            return await self.send_family_alert(alert_data, **context)
        
        elif "dashboard" in task:
            group_id = context.get("group_id", "")
            if group_id:
                return await self.get_family_dashboard(group_id, **context)
            else:
                return {
                    "operation": "get_family_dashboard",
                    "status": "failed",
                    "error": "Group ID is required"
                }
        
        elif "family" in task:
            # General family safety info
            return {
                "operation": "family_safety_info",
                "status": "completed",
                "features": [
                    "Family group creation and management",
                    "Multi-member journey tracking",
                    "Group safety alerts and notifications",
                    "Shared emergency contacts",
                    "Location sharing between members",
                    "Check-in reminders and tracking",
                    "Sathi assignment for family groups"
                ],
                "safety_tips": [
                    "Create a family group for all traveling members",
                    "Enable location sharing for real-time tracking",
                    "Set up check-in intervals for long journeys",
                    "Add emergency contacts accessible to all members",
                    "Use Sathi service for enhanced family safety",
                    "Enable all notification types for critical alerts"
                ]
            }
        
        else:
            return {
                "operation": "unknown",
                "status": "failed",
                "error": f"Unknown family safety task: {task}"
            }
