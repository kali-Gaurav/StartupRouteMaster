"""
SOS Handler
===========
Handles emergency SOS requests with location sharing.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any, List
from dataclasses import dataclass

from ..schemas import (
    TelegramMessage, UserContext, BotResponse, 
    IntentType
)
from ..command_router import HandlerResult, HandlerResultStatus
from ..dispatcher import telegram_dispatcher
from ..keyboards import keyboard_builder
from ..user_session_manager import user_session_manager
from ..config import feature_config

logger = logging.getLogger(__name__)


@dataclass
class SOSLocation:
    """SOS location data."""
    latitude: float
    longitude: float
    accuracy: Optional[float] = None
    timestamp: Optional[datetime] = None


class SOSHandler:
    """Handles SOS emergency requests."""
    
    # Emergency contacts (would be loaded from database)
    EMERGENCY_HELPLINES = {
        "railway": "139",
        "police": "112",
        "women_helpline": "1091",
        "child_helpline": "1098",
        "ambulance": "108"
    }
    
    async def handle(
        self,
        message: TelegramMessage,
        context: UserContext,
        intent_result
    ) -> HandlerResult:
        """
        Handle SOS requests.
        
        Args:
            message: Incoming message
            context: User context
            intent_result: Intent classification result
            
        Returns:
            HandlerResult with response
        """
        chat_id = message.chat.id
        text = (message.text or "").lower()
        
        try:
            # Check for location data
            if message.location:
                return await self._handle_location_share(chat_id, message.location, context)
            
            # Check for immediate SOS trigger
            if "sos" in text or "emergency" in text or "danger" in text:
                return await self._show_sos_menu(chat_id, context)
            
            # Check safety status
            if "safety" in text or "status" in text:
                return await self._check_safety_status(chat_id, context)
            
            # Default SOS menu
            return await self._show_sos_menu(chat_id, context)
            
        except Exception as e:
            logger.error(f"Error in SOS handler: {e}")
            return HandlerResult(
                status=HandlerResultStatus.FAILED,
                response=BotResponse(
                    chat_id=chat_id,
                    text=f"❌ <b>Error</b>\n\n{str(e)}"
                ),
                error=str(e)
            )
    
    async def _show_sos_menu(
        self,
        chat_id: int,
        context: UserContext
    ) -> HandlerResult:
        """Show SOS emergency menu."""
        text = """🚨 <b>Emergency SOS</b>

━━━━━━━━━━━━━━━━━━━━━━━━

⚠️ <b>Immediate Assistance Required?</b>

Tap <b>"🚨 Send SOS"</b> to:
• Alert emergency contacts
• Share live location
• Notify railway authorities

━━━━━━━━━━━━━━━━━━━━━━━━

<b>Quick Actions:</b>

📍 <b>Share Location</b>
   Send your current location

📞 <b>Helpline</b>
   Call railway helpline 139

🆘 <b>Get Help</b>
   View emergency options

━━━━━━━━━━━━━━━━━━━━━━━━

<i>Use only in genuine emergencies.</i>"""
        
        return HandlerResult(
            status=HandlerResultStatus.SUCCESS,
            response=BotResponse(
                chat_id=chat_id,
                text=text,
                inline_keyboards=keyboard_builder.sos_emergency()
            ),
            next_state="sos",
            data={"sos_step": "menu"}
        )
    
    async def _handle_location_share(
        self,
        chat_id: int,
        location: Dict[str, float],
        context: UserContext
    ) -> HandlerResult:
        """Handle location sharing from user."""
        try:
            # Store location
            sos_location = SOSLocation(
                latitude=location["latitude"],
                longitude=location["longitude"],
                accuracy=location.get("accuracy"),
                timestamp=datetime.utcnow()
            )
            
            # Update context
            context.data["sos_location"] = {
                "lat": sos_location.latitude,
                "lng": sos_location.longitude,
                "timestamp": sos_location.timestamp.isoformat()
            }
            
            # Generate location URL
            maps_url = f"https://www.google.com/maps/search/?api=1&query={sos_location.latitude},{sos_location.longitude}"
            
            text = f"""📍 <b>Location Received</b>

<b>Coordinates:</b>
Lat: {sos_location.latitude}
Lng: {sos_location.longitude}

[View on Map]({maps_url})

━━━━━━━━━━━━━━━━━━━━━━━━

<b>What would you like to do?</b>

• 🚨 Send SOS Alert
• 📞 Call Helpline
• 🆘 Get Help

<i>Your location will be shared with emergency contacts.</i>"""
            
            return HandlerResult(
                status=HandlerResultStatus.SUCCESS,
                response=BotResponse(
                    chat_id=chat_id,
                    text=text,
                    inline_keyboards=[
                        [
                            {"text": "🚨 Send SOS", "callback_data": "sos_send_with_loc"},
                            {"text": "📞 Call 139", "callback_data": "sos_call"}
                        ],
                        [
                            {"text": "🔙 Cancel", "callback_data": "sos_cancel"}
                        ]
                    ]
                ),
                next_state="sos",
                data={
                    "sos_step": "location_received",
                    "sos_location": context.data.get("sos_location")
                }
            )
            
        except Exception as e:
            logger.error(f"Error handling location: {e}")
            return HandlerResult(
                status=HandlerResultStatus.FAILED,
                response=BotResponse(
                    chat_id=chat_id,
                    text="❌ <b>Error processing location</b>\n\nPlease try again."
                )
            )
    
    async def _send_sos_alert(
        self,
        chat_id: int,
        context: UserContext
    ) -> HandlerResult:
        """Send SOS alert to emergency contacts."""
        try:
            # Get location from context
            location_data = context.data.get("sos_location", {})
            lat = location_data.get("lat", 0)
            lng = location_data.get("lng", 0)
            
            # Get user info
            user_info = context.data.get("user_info", {})
            user_name = user_info.get("name", "Unknown User")
            phone = user_info.get("phone", "Not available")
            
            # Generate maps URL
            maps_url = f"https://www.google.com/maps/search/?api=1&query={lat},{lng}"
            
            # Prepare SOS message
            sos_message = self._create_sos_message(user_name, phone, lat, lng, maps_url)
            
            # Get emergency contacts
            contacts = await self._get_emergency_contacts(chat_id)
            
            # Send alerts
            results = await self._dispatch_sos_alerts(
                chat_id, sos_message, contacts
            )
            
            # Log SOS
            logger.warning(f"SOS alert sent by user {chat_id}: {results}")
            
            # Confirm to user
            text = f"""🚨 <b>SOS Alert Sent!</b>

━━━━━━━━━━━━━━━━━━━━━━━━

✅ <b>Alert sent to {results['success']} contacts</b>
❌ <b>{results['failed']} failed</b>

📍 Location shared with emergency contacts.

<b>Immediate Actions:</b>

📞 <b>Railway Helpline: 139</b>
🚔 <b>Police: 112</b>
🚑 <b>Ambulance: 108</b>

<i>Help is on the way. Stay calm.</i>

━━━━━━━━━━━━━━━━━━━━━━━━

<b>Track your location:</b>
[View on Map]({maps_url})"""
            
            return HandlerResult(
                status=HandlerResultStatus.SUCCESS,
                response=BotResponse(
                    chat_id=chat_id,
                    text=text,
                    inline_keyboards=[
                        [
                            {"text": "📞 Call 139", "callback_data": "sos_call_139"},
                            {"text": "📞 Call 112", "callback_data": "sos_call_112"}
                        ],
                        [
                            {"text": "🔄 Update Location", "callback_data": "sos_update_loc"},
                            {"text": "✅ I'm Safe", "callback_data": "sos_safe"}
                        ]
                    ]
                ),
                next_state="sos_active",
                data={
                    "sos_step": "sent",
                    "sos_sent_at": datetime.utcnow().isoformat(),
                    "sos_results": results
                }
            )
            
        except Exception as e:
            logger.error(f"Error sending SOS: {e}")
            return HandlerResult(
                status=HandlerResultStatus.FAILED,
                response=BotResponse(
                    chat_id=chat_id,
                    text=f"❌ <b>SOS Failed</b>\n\n{str(e)}\n\nPlease call emergency numbers directly: 139 (Railway), 112 (Police)"
                ),
                error=str(e)
            )
    
    def _create_sos_message(
        self,
        user_name: str,
        phone: str,
        lat: float,
        lng: float,
        maps_url: str
    ) -> str:
        """Create SOS alert message."""
        return (
            f"🚨 <b>EMERGENCY SOS ALERT</b> 🚨\n\n"
            f"<b>Person:</b> {user_name}\n"
            f"<b>Phone:</b> {phone}\n"
            f"<b>Location:</b> [{lat}, {lng}]({maps_url})\n"
            f"<b>Time:</b> {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n\n"
            f"⚠️ <b>URGENT ASSISTANCE REQUIRED</b>\n\n"
            f"Please contact immediately and alert authorities if needed."
        )
    
    async def _get_emergency_contacts(self, chat_id: int) -> List[Dict[str, Any]]:
        """Get user's emergency contacts."""
        try:
            # This would fetch from database
            # For now, return mock data
            return [
                {
                    "name": "Primary Contact",
                    "phone": "+91XXXXXXXXXX",
                    "telegram_id": None
                },
                {
                    "name": "Secondary Contact",
                    "phone": "+91XXXXXXXXXX",
                    "telegram_id": None
                }
            ]
        except Exception as e:
            logger.error(f"Error getting emergency contacts: {e}")
            return []
    
    async def _dispatch_sos_alerts(
        self,
        chat_id: int,
        message: str,
        contacts: List[Dict[str, Any]]
    ) -> Dict[str, int]:
        """Dispatch SOS alerts to contacts."""
        results = {"success": 0, "failed": 0}
        
        # Send to Telegram contacts
        for contact in contacts:
            if contact.get("telegram_id"):
                success = await telegram_dispatcher.send_message(
                    chat_id=contact["telegram_id"],
                    text=message
                )
                if success:
                    results["success"] += 1
                else:
                    results["failed"] += 1
        
        # Also send to railway emergency channel if configured
        # This would be a configured channel ID
        # await telegram_dispatcher.send_message(channel_id, message)
        
        return results
    
    async def _check_safety_status(
        self,
        chat_id: int,
        context: UserContext
    ) -> HandlerResult:
        """Check safety status of user."""
        try:
            # Get current location from context
            location_data = context.data.get("sos_location", {})
            
            if not location_data:
                text = """🛡️ <b>Safety Check</b>

━━━━━━━━━━━━━━━━━━━━━━━━

📍 <b>Location Status:</b> Not shared

To check your safety status, please share your location.

<i>Tap 📍 Share Location below</i>"""
                
                return HandlerResult(
                    status=HandlerResultStatus.NEEDS_INPUT,
                    response=BotResponse(
                        chat_id=chat_id,
                        text=text,
                        inline_keyboards=[
                            [
                                {"text": "📍 Share Location", "callback_data": "sos_share_loc"}
                            ],
                            [
                                {"text": "🔙 Back", "callback_data": "sos_back"}
                            ]
                        ]
                    ),
                    next_state="sos"
                )
            
            # Get safety info based on location
            lat = location_data.get("lat", 0)
            lng = location_data.get("lng", 0)
            
            # This would integrate with safety services
            safety_info = await self._get_safety_info(lat, lng)
            
            text = f"""🛡️ <b>Safety Status</b>

━━━━━━━━━━━━━━━━━━━━━━━━

📍 <b>Current Location:</b>
Lat: {lat}, Lng: {lng}

🚂 <b>Nearest Station:</b> {safety_info.get('nearest_station', 'N/A')}
📏 <b>Distance:</b> {safety_info.get('distance', 'N/A')}

🏥 <b>Nearest Hospital:</b> {safety_info.get('hospital', 'N/A')}
🚔 <b>Nearest Police:</b> {safety_info.get('police', 'N/A')}

📞 <b>Emergency Numbers:</b>
• Railway: 139
• Police: 112
• Ambulance: 108

━━━━━━━━━━━━━━━━━━━━━━━━

<i>Stay safe! If you need help, tap 🚨 SOS.</i>"""
            
            return HandlerResult(
                status=HandlerResultStatus.SUCCESS,
                response=BotResponse(
                    chat_id=chat_id,
                    text=text,
                    inline_keyboard=[
                        [
                            {"text": "🚨 SOS", "callback_data": "sos_send"},
                            {"text": "📞 Call 139", "callback_data": "sos_call"}
                        ],
                        [
                            {"text": "🔄 Update Location", "callback_data": "sos_update_loc"},
                            {"text": "🔙 Back", "callback_data": "sos_back"}
                        ]
                    ]
                ),
                next_state="sos",
                data={"safety_info": safety_info}
            )
            
        except Exception as e:
            logger.error(f"Error checking safety status: {e}")
            return HandlerResult(
                status=HandlerResultStatus.FAILED,
                response=BotResponse(
                    chat_id=chat_id,
                    text="❌ <b>Error checking safety</b>\n\nPlease try again."
                )
            )
    
    async def _get_safety_info(
        self,
        lat: float,
        lng: float
    ) -> Dict[str, str]:
        """Get safety information for location."""
        # This would integrate with external services
        # For now, return mock data
        return {
            "nearest_station": "Mumbai Central",
            "distance": "2.5 km",
            "hospital": "Bombay Hospital",
            "police": "Mumbai Police Station"
        }
    
    async def handle_callback(
        self,
        callback_data: str,
        chat_id: int,
        context: UserContext
    ) -> HandlerResult:
        """Handle SOS callbacks."""
        try:
            action = callback_data
            
            if action == "sos_send" or action == "sos_send_with_loc":
                # Check if we have location
                if not context.data.get("sos_location"):
                    # Request location
                    return HandlerResult(
                        status=HandlerResultStatus.NEEDS_INPUT,
                        response=BotResponse(
                            chat_id=chat_id,
                            text="📍 <b>Share Location</b>\n\nPlease share your location to send SOS alert.",
                            inline_keyboards=[
                                [
                                    {"text": "📍 Share Live Location", "callback_data": "sos_share_live"},
                                    {"text": "📍 Share Current Location", "callback_data": "sos_share_current"}
                                ],
                                [
                                    {"text": "🔙 Cancel", "callback_data": "sos_cancel"}
                                ]
                            ]
                        ),
                        next_state="sos"
                    )
                return await self._send_sos_alert(chat_id, context)
            
            elif action == "sos_location":
                return await self._handle_location_share(
                    chat_id, 
                    context.data.get("sos_location", {}),
                    context
                )
            
            elif action == "sos_call" or action == "sos_call_139":
                return HandlerResult(
                    status=HandlerResultStatus.SUCCESS,
                    response=BotResponse(
                        chat_id=chat_id,
                        text="""📞 <b>Railway Helpline</b>

━━━━━━━━━━━━━━━━━━━━━━━━

<b>Call 139</b> for:
• Railway accidents
• Medical emergencies
• Security issues
• General assistance

<i>Dial now or tap below</i>""",
                        inline_keyboards=[
                            [
                                {"text": "📞 Call 139", "url": "tel:139"}
                            ],
                            [
                                {"text": "🔙 Back", "callback_data": "sos_back"}
                            ]
                        ]
                    )
                )
            
            elif action == "sos_call_112":
                return HandlerResult(
                    status=HandlerResultStatus.SUCCESS,
                    response=BotResponse(
                        chat_id=chat_id,
                        text="""📞 <b>Emergency Number</b>

━━━━━━━━━━━━━━━━━━━━━━━━

<b>Call 112</b> for:
• Police
• Fire
• Ambulance
• All emergencies

<i>Dial now or tap below</i>""",
                        inline_keyboards=[
                            [
                                {"text": "📞 Call 112", "url": "tel:112"}
                            ]
                        ]
                    )
                )
            
            elif action == "sos_cancel":
                return HandlerResult(
                    status=HandlerResultStatus.SUCCESS,
                    response=BotResponse(
                        chat_id=chat_id,
                        text="✅ <b>SOS Cancelled</b>\n\nNo alert has been sent.",
                        keyboard=keyboard_builder.main_menu()
                    ),
                    next_state="idle"
                )
            
            elif action == "sos_safe":
                return HandlerResult(
                    status=HandlerResultStatus.SUCCESS,
                    response=BotResponse(
                        chat_id=chat_id,
                        text="✅ <b>Safety Confirmed</b>\n\nGlad you're safe!\n\nIf you need any assistance, I'm here to help.",
                        keyboard=keyboard_builder.main_menu()
                    ),
                    next_state="idle"
                )
            
            elif action == "sos_share_loc" or action == "sos_share_current":
                return HandlerResult(
                    status=HandlerResultStatus.NEEDS_INPUT,
                    response=BotResponse(
                        chat_id=chat_id,
                        text="📍 <b>Share Location</b>\n\nPlease tap the button below to share your location.",
                        inline_keyboards=[
                            [
                                {"text": "📍 Send Location", "callback_data": "sos_location_received"}
                            ]
                        ]
                    ),
                    next_state="sos"
                )
            
            elif action == "sos_back":
                return await self._show_sos_menu(chat_id, context)
            
            return HandlerResult(
                status=HandlerResultStatus.SUCCESS,
                response=BotResponse(
                    chat_id=chat_id,
                    text="Processing..."
                )
            )
            
        except Exception as e:
            logger.error(f"Error in SOS callback: {e}")
            return HandlerResult(
                status=HandlerResultStatus.FAILED,
                error=str(e)
            )


# Global instance
sos_handler = SOSHandler()
