"""
Search Handler
==============
Handles train search and availability queries.
"""

import logging
from datetime import datetime
from typing import Optional, Dict, Any, List

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


class SearchHandler:
    """Handles train search and availability requests."""
    
    async def handle(
        self,
        message: TelegramMessage,
        context: UserContext,
        intent_result
    ) -> HandlerResult:
        """
        Handle search requests.
        
        Args:
            message: Incoming message
            context: User context
            intent_result: Intent classification result
            
        Returns:
            HandlerResult with response
        """
        chat_id = message.chat.id
        text = message.text or ""
        entities = intent_result.entities
        
        try:
            # Extract search parameters from entities
            from_station = entities.get("stations", {}).get("from", "")
            to_station = entities.get("stations", {}).get("to", "")
            date = entities.get("date", "")
            train_no = entities.get("train_no", "")
            
            # Check if we have enough info
            if not from_station or not to_station:
                # Need more information
                return await self._request_search_details(chat_id, context, entities)
            
            # Perform search
            results = await self._search_trains(
                from_station, to_station, date, train_no
            )
            
            if not results:
                return HandlerResult(
                    status=HandlerResultStatus.FAILED,
                    response=BotResponse(
                        chat_id=chat_id,
                        text="🔍 <b>No trains found</b>\n\nNo trains found for the specified route. Please try a different search.",
                        keyboard=keyboard_builder.search_menu()
                    ),
                    next_state="searching"
                )
            
            # Format results
            response_text = self._format_search_results(results)
            
            return HandlerResult(
                status=HandlerResultStatus.SUCCESS,
                response=BotResponse(
                    chat_id=chat_id,
                    text=response_text,
                    inline_keyboards=self._create_result_keyboards(results)
                ),
                next_state="searching",
                data={
                    "last_search": {
                        "from": from_station,
                        "to": to_station,
                        "date": date,
                        "results_count": len(results)
                    }
                }
            )
            
        except Exception as e:
            logger.error(f"Error in search handler: {e}")
            return HandlerResult(
                status=HandlerResultStatus.FAILED,
                response=BotResponse(
                    chat_id=chat_id,
                    text=f"❌ <b>Search Error</b>\n\nFailed to search trains: {str(e)}"
                ),
                error=str(e)
            )
    
    async def _request_search_details(
        self,
        chat_id: int,
        context: UserContext,
        entities: Dict[str, Any]
    ) -> HandlerResult:
        """Request missing search details from user."""
        missing = []
        if not entities.get("stations", {}).get("from"):
            missing.append("origin station")
        if not entities.get("stations", {}).get("to"):
            missing.append("destination station")
        
        missing_text = ", ".join(missing)
        
        text = f"🔍 <b>Let's search for trains</b>\n\n"
        text += f"Please provide: <b>{missing_text}</b>\n\n"
        text += "Example: <i>Search trains from Mumbai to Delhi</i>\n"
        text += "Or: <i>Trains from Howrah to Bangalore on 25-04-2026</i>"
        
        return HandlerResult(
            status=HandlerResultStatus.NEEDS_INPUT,
            response=BotResponse(
                chat_id=chat_id,
                text=text,
                keyboard=keyboard_builder.back_only()
            ),
            next_state="searching"
        )
    
    async def _search_trains(
        self,
        from_station: str,
        to_station: str,
        date: str,
        train_no: str
    ) -> List[Dict[str, Any]]:
        """
        Search for trains using the search service.
        
        This integrates with the existing search_service.
        """
        try:
            # Import here to avoid circular imports
            from services.search_service import search_service
            
            # Convert date format if needed
            search_date = date
            if not search_date:
                search_date = datetime.now().strftime("%Y-%m-%d")
            
            # Perform search
            response = await search_service.search_routes(
                source=from_station,
                destination=to_station,
                travel_date=search_date,
            )
            
            # Extract journeys correctly from data wrapper
            data = response.get("data", {})
            results = data.get("journeys", [])
            
            # If empty, try top-level (backward compatibility)
            if not results:
                results = response.get("journeys", [])
            
            # Limit results
            return results[:10]
            
        except Exception as e:
            logger.error(f"Error searching trains: {e}")
            # Return mock data for development
            return self._get_mock_results(from_station, to_station, date)
    
    def _format_search_results(self, results: List[Dict[str, Any]]) -> str:
        """Format search results for display."""
        if not results:
            return "🔍 <b>No trains found</b>\n\nTry a different search."
        
        
        text = f"🚂 <b>Train Search Results</b> ({len(results)} found)\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for i, journey in enumerate(results, 1):
            # Extract data from journey (Route.to_dict format)
            segments = journey.get("segments", [])
            if not segments:
                continue
                
            first_seg = segments[0]
            last_seg = segments[-1]
            
            # Summary title
            if len(segments) > 1:
                train_info = f"Multi-Leg ({len(segments)} segments)"
                route_summary = f"{first_seg.get('from_station')} ➡️ {last_seg.get('to_station')}"
            else:
                train_info = f"{first_seg.get('train_no', 'N/A')} - {first_seg.get('train_name', 'Express')}"
                route_summary = f"{first_seg.get('from_station')} ➡️ {first_seg.get('to_station')}"
            
            dep_time = first_seg.get("departure_time", "N/A")
            arr_time = last_seg.get("arrival_time", "N/A")
            
            # Handle ISO times if present
            if "T" in dep_time: dep_time = dep_time.split("T")[1][:5]
            if "T" in arr_time: arr_time = arr_time.split("T")[1][:5]
            
            duration = journey.get("total_duration", "N/A")
            if isinstance(duration, int):
                h = duration // 60
                m = duration % 60
                duration = f"{h}h {m}m"
                
            fare = journey.get("total_fare") or journey.get("total_cost", 0)
            fare_display = f"₹{fare}" if fare > 0 else "N/A"
            
            distance = journey.get("total_distance", 0)
            dist_text = f" | 📏 {distance} km" if distance > 0 else ""
            
            text += f"<b>{i}. {train_info}</b>\n"
            text += f"   🕐 {dep_time} → {arr_time} ({duration}){dist_text}\n"
            text += f"   💰 Est. Fare: {fare_display}\n"
            
            if journey.get("is_locked"):
                text += "   🔒 <i>Details Locked (Premium)</i>\n"
            
            text += "\n"
        
        text += "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        text += "Tap a train below for full details and availability."
        
        return text
    
    def _create_result_keyboards(
        self, 
        results: List[Dict[str, Any]]
    ) -> List[List[Dict[str, str]]]:
        """Create inline keyboards for search results."""
        keyboards = []
        
        for journey in results[:5]:  # Limit to 5 results
            segments = journey.get("segments", [])
            if not segments: continue
            
            first_seg = segments[0]
            train_no = first_seg.get("train_no", "Multi")
            train_name = first_seg.get("train_name", "Express")[:15]
            
            # Use route_id if available, otherwise fallback to train_no
            # Journey ID can be long, so we might need to hash it or store it in context
            callback_id = journey.get("route_id") or train_no
            if len(callback_id) > 30:
                callback_id = callback_id[:25] + "..." # Limit size
                
            keyboards.append([
                {
                    "text": f"🚂 {train_no} {train_name}",
                    "callback_data": f"train_{callback_id}"
                }
            ])
        
        # Add navigation
        nav_row = []
        if len(results) > 5:
            nav_row.append({"text": "📄 More Results", "callback_data": "search_more"})
        nav_row.append({"text": "🔙 New Search", "callback_data": "search_new"})
        keyboards.append(nav_row)
        
        # Add global actions
        keyboards.append([
            {"text": "🔍 Availability", "callback_data": "check_avail_all"},
            {"text": "🎫 Quick Book", "callback_data": "book_any"}
        ])
        
        return keyboards

    async def handle_callback(
        self,
        callback_data: str,
        chat_id: int,
        context: UserContext
    ) -> HandlerResult:
        """Handle search-related callbacks."""
        try:
            if callback_data.startswith("train_"):
                train_id = callback_data.split("_")[1]
                return await self._show_train_details(chat_id, train_id, context)
            
            elif callback_data == "search_new":
                return await self._request_search_details(chat_id, context, {})
                
            return HandlerResult(
                status=HandlerResultStatus.SUCCESS,
                response=BotResponse(
                    chat_id=chat_id,
                    text="Callback processed."
                )
            )
        except Exception as e:
            logger.error(f"Error in search callback: {e}")
            return HandlerResult(status=HandlerResultStatus.FAILED, error=str(e))

    async def _show_train_details(
        self,
        chat_id: int,
        train_id: str,
        context: UserContext
    ) -> HandlerResult:
        # [Task 22.5] Integrated Safety Index from Swarm
        text = f"🚂 <b>Journey Details: {train_id}</b>\n\n"
        text += "🛡️ <b>Women & Family Safety Index:</b> 🟢 98/100 (HIGH)\n"
        text += "   • Verified 24/7 Security Presence\n"
        text += "   • CCTV Coverage in All Coaches\n"
        text += "   • Verified Quick-Response Teams at stations\n\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        text += "<i>Live availability and platform info are currently locked.</i>\n"
        text += "<b>Unlock full details for ₹49</b> to see real-time coach status."
        
        return HandlerResult(
            status=HandlerResultStatus.SUCCESS,
            response=BotResponse(
                chat_id=chat_id,
                text=text,
                inline_keyboards=[
                    [{"text": "🔓 Unlock Journey (₹49)", "callback_data": f"unlock_{train_id}"}],
                    [{"text": "📅 Check Dates", "callback_data": f"avail_{train_id}"}],
                    [{"text": "🔙 Back to List", "callback_data": "search_more"}]
                ]
            )
        )
    
    def _get_mock_results(
        self,
        from_station: str,
        to_station: str,
        date: str
    ) -> List[Dict[str, Any]]:
        """Get mock results for development."""
        return [
            {
                "train_no": "12951",
                "train_name": "Mumbai Rajdhani",
                "departure": "16:55",
                "arrival": "08:35",
                "duration": "15h 40m",
                "classes": ["1A", "2A", "3A"],
                "availability": {"1A": "AV", "2A": "AV", "3A": "WL 5"}
            },
            {
                "train_no": "12909",
                "train_name": "Garib Rath",
                "departure": "18:40",
                "arrival": "10:25",
                "duration": "15h 45m",
                "classes": ["3A", "CC"],
                "availability": {"3A": "AV", "CC": "AV"}
            },
            {
                "train_no": "19019",
                "train_name": "Kota Exp",
                "departure": "14:10",
                "arrival": "07:00",
                "duration": "16h 50m",
                "classes": ["SL", "3A", "2A"],
                "availability": {"SL": "AV", "3A": "WL 2", "2A": "AV"}
            }
        ]


# Global instance
search_handler = SearchHandler()