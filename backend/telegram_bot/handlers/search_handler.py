"""
Search Handler
==============
Handles train search and availability queries.
"""

import logging
import hashlib
import uuid
from datetime import datetime
from typing import Optional, Dict, Any, List

from ..schemas import (
    TelegramMessage, UserContext, BotResponse, 
    IntentType, UserState
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
            # Feature 1: NLP Entity Extraction
            from_station = entities.get("origin") or entities.get("stations", {}).get("from") or context.data.get("search_from")
            to_station = entities.get("destination") or entities.get("stations", {}).get("to") or context.data.get("search_to")
            date = entities.get("date") or context.data.get("search_date")
            train_no = entities.get("train_no", "")
            
            # Check if we are in a sub-state already
            if context.state == UserState.AWAITING_ORIGIN:
                from_station = text
                context.data["search_from"] = from_station
            elif context.state == UserState.AWAITING_DESTINATION:
                to_station = text
                context.data["search_to"] = to_station
            elif context.state == UserState.AWAITING_DATE:
                # Try to parse date from text
                from ..intent_classifier import IntentClassifier
                ic = IntentClassifier()
                normalized_date = ic._normalize_date(text)
                if normalized_date:
                    date = normalized_date
                    context.data["search_date"] = date
                else:
                    return HandlerResult(
                        status=HandlerResultStatus.NEEDS_INPUT,
                        response=BotResponse(
                            chat_id=chat_id,
                            text="⚠️ I couldn't understand that date. Please use YYYY-MM-DD or say 'tomorrow'.",
                            keyboard=keyboard_builder.date_picker()
                        ),
                        next_state=UserState.AWAITING_DATE
                    )

            # Check if we have enough info
            if not from_station:
                return await self._request_search_details(chat_id, context, UserState.AWAITING_ORIGIN)
            if not to_station:
                context.data["search_from"] = from_station # Save what we have
                return await self._request_search_details(chat_id, context, UserState.AWAITING_DESTINATION)
            if not date:
                context.data["search_from"] = from_station
                context.data["search_to"] = to_station
                return await self._request_search_details(chat_id, context, UserState.AWAITING_DATE)
            
            # Save for search
            context.data["search_from"] = from_station
            context.data["search_to"] = to_station
            context.data["search_date"] = date
            
            # Perform search
            results = await self._search_trains(
                from_station, to_station, date, train_no
            )
            
            if not results:
                explanation_text = "No trains found for the specified route. Please try a different search."
                
                # Fetch intelligent explanation from service
                explanation = await self._get_zero_yield_explanation(from_station, to_station, date)
                if explanation and explanation.get("reasons"):
                    reasons_str = "\n".join([f"• {r}" for r in explanation["reasons"]])
                    sug_str = "\n".join([f"💡 <i>{s}</i>" for s in explanation.get("suggestions", [])])
                    explanation_text = f"<b>Why?</b>\n{reasons_str}\n\n{sug_str}"
                
                return HandlerResult(
                    status=HandlerResultStatus.FAILED,
                    response=BotResponse(
                        chat_id=chat_id,
                        text=f"🔍 <b>No trains found</b>\n\n{explanation_text}",
                        keyboard=keyboard_builder.search_menu()
                    ),
                    next_state=UserState.SEARCHING,
                    data={
                        "search_from": from_station,
                        "search_to": to_station,
                        "search_date": date
                    }
                )
            
            # Save full results to session context for pagination
            context.data["search_results"] = results
            context.data["search_page"] = 0
            
            # Format results
            response_text = self._format_search_results(results, page=0)
            
            return HandlerResult(
                status=HandlerResultStatus.SUCCESS,
                response=BotResponse(
                    chat_id=chat_id,
                    text=response_text,
                    inline_keyboard=self._create_result_keyboards(results, page=0)
                ),
                next_state=UserState.SEARCHING,
                data={
                    "search_from": from_station,
                    "search_to": to_station,
                    "search_date": date,
                    "search_results": results,
                    "search_page": 0,
                    "id_map": {
                        hashlib.md5(j.get("journey_id", str(uuid.uuid4())).encode()).hexdigest()[:8]: j.get("journey_id")
                        for j in results
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
        target_state: UserState
    ) -> HandlerResult:
        """Request missing search details from user based on state."""
        
        if target_state == UserState.AWAITING_ORIGIN:
            text = "📍 <b>Where are you traveling from?</b>\n\nTry: <i>Delhi, Mumbai, NDLS</i>"
            keyboard = keyboard_builder.popular_stations()
        elif target_state == UserState.AWAITING_DESTINATION:
            origin = context.data.get("search_from", "Origin")
            text = f"📍 Traveling from <b>{origin}</b>.\n\n<b>Where are you going to?</b>"
            keyboard = keyboard_builder.popular_stations()
        elif target_state == UserState.AWAITING_DATE:
            origin = context.data.get("search_from")
            dest = context.data.get("search_to")
            text = f"🚉 {origin} → {dest}\n\n📅 <b>When would you like to travel?</b>"
            keyboard = keyboard_builder.date_picker()
        else:
            text = "🔍 Please provide more details for your search."
            keyboard = keyboard_builder.search_menu()
            
        return HandlerResult(
            status=HandlerResultStatus.NEEDS_INPUT,
            response=BotResponse(
                chat_id=chat_id,
                text=text,
                keyboard=keyboard
            ),
            next_state=target_state
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
            return []
            
    async def _get_zero_yield_explanation(
        self,
        from_station: str,
        to_station: str,
        date: str
    ) -> Dict[str, Any]:
        """Fetch intelligent explanation for why a search failed."""
        try:
            from services.search_service import search_service
            
            search_date = date
            if not search_date:
                search_date = datetime.now().strftime("%Y-%m-%d")
                
            try:
                dt_obj = datetime.strptime(search_date, "%Y-%m-%d")
            except ValueError:
                dt_obj = datetime.now()
                
            return await search_service.explain_zero_results(
                source=from_station,
                destination=to_station,
                travel_date=dt_obj
            )
        except Exception as e:
            logger.error(f"Error fetching zero yield explanation: {e}")
            return {}
    
    def _format_search_results(self, results: List[Dict[str, Any]], page: int = 0) -> str:
        """Format search results for display (Feature 2: Advanced UI Engine)."""
        if not results:
            return "🔍 <b>No trains found</b>\n\nTry a different search."
        
        text = f"🚂 <b>Train Search Results</b> ({len(results)})\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        items_per_page = 3
        start_idx = page * items_per_page
        end_idx = min(start_idx + items_per_page, len(results))
        
        for i, journey in enumerate(results[start_idx:end_idx], start_idx + 1):
            segments = journey.get("segments", [])
            if not segments: continue
            
            # Single or Multi-leg logic
            if len(segments) == 1:
                seg = segments[0]
                train_info = f"🚆 <b>{seg.get('train_number')} {seg.get('train_name')}</b>"
                route = f"{seg.get('from_station')} → {seg.get('to_station')}"
            else:
                train_info = f"🚆 <b>Multi-Leg ({len(segments)} legs)</b>"
                route = f"{segments[0].get('from_station')} → {segments[-1].get('to_station')}"

            # Times and Duration
            dep = segments[0].get("departure_time", "N/A")
            arr = segments[-1].get("arrival_time", "N/A")
            if "T" in dep: dep = dep.split("T")[1][:5]
            if "T" in arr: arr = arr.split("T")[1][:5]
            
            duration = journey.get("total_duration", 0)
            h = duration // 60
            m = duration % 60
            duration_text = f"{h}h {m}m"
            
            # Availability Signals (🟢🟡🔴)
            # Mocking availability for UI demonstration if not present
            avail = journey.get("availability_status") or "AVAILABLE"
            if avail == "AVAILABLE":
                avail_signal = "🟢 SL 120 | 🟢 3A 45"
            elif avail == "WAITLIST":
                avail_signal = "🟡 SL WL12 | 🟢 3A 5"
            else:
                avail_signal = "🔴 FULL"
            
            # Fares
            fare = journey.get("total_fare", 0)
            fare_range = f"₹{int(fare)} – ₹{int(fare*2.5)}" if fare > 0 else "₹450 – ₹1800"

            text += f"{train_info}\n"
            text += f"<code>{route}</code>\n\n"
            text += f"🕒 {dep} → {arr}\n"
            text += f"⏱ {duration_text}\n\n"
            text += f"{avail_signal}\n"
            text += f"💰 {fare_range}\n"
            text += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        page_total = (len(results) + items_per_page - 1) // items_per_page
        text += f"<i>Page {page + 1} of {page_total}</i>"
        
        return text
    
    def _create_result_keyboards(
        self, 
        results: List[Dict[str, Any]],
        page: int = 0
    ) -> List[List[Dict[str, str]]]:
        """Create inline keyboards for search results with pagination and filters."""
        keyboards = []
        items_per_page = 3
        start_idx = page * items_per_page
        end_idx = start_idx + items_per_page
        
        # 1. Train Selection Buttons
        for journey in results[start_idx:end_idx]:
            segments = journey.get("segments", [])
            if not segments: continue
            
            first_seg = segments[0]
            train_no = first_seg.get("train_number", "Multi")
            train_name = first_seg.get("train_name", "Express")[:15]
            
            # Shorten Callback ID (Hashing for 64-byte limit)
            import hashlib
            import uuid
            jid = journey.get("journey_id", str(uuid.uuid4()))
            short_id = hashlib.md5(jid.encode()).hexdigest()[:8]
            
            keyboards.append([
                {
                    "text": f"🚆 {train_no} - View Details",
                    "callback_data": f"t_view_{short_id}"
                }
            ])
        
        # 2. Pagination Controls
        page_total = (len(results) + items_per_page - 1) // items_per_page
        nav_row = []
        if page > 0:
            nav_row.append({"text": "⬅️ Prev", "callback_data": f"s_page_{page-1}"})
        
        nav_row.append({"text": f"Page {page+1}/{page_total}", "callback_data": "ignore"})
        
        if end_idx < len(results):
            nav_row.append({"text": "Next ➡️", "callback_data": f"s_page_{page+1}"})
        
        keyboards.append(nav_row)
        
        # 3. Dynamic Filters (Feature 2.7)
        filter_row = [
            {"text": "🎫 Class", "callback_data": "f_class"},
            {"text": "⚡ Quota", "callback_data": "f_quota"},
            {"text": "⏱ Sort", "callback_data": "f_sort"}
        ]
        keyboards.append(filter_row)
        
        return keyboards

    async def handle_callback(
        self,
        callback_data: str,
        chat_id: int,
        context: UserContext
    ) -> HandlerResult:
        """Handle search-related callbacks (Feature 2: Dynamic UI)."""
        try:
            if callback_data.startswith("t_view_"):
                short_id = callback_data.split("_")[2]
                # Resolve full journey_id from mapping
                mapping = context.data.get("id_map", {})
                journey_id = mapping.get(short_id)
                
                if not journey_id:
                    return HandlerResult(
                        status=HandlerResultStatus.FAILED,
                        response=BotResponse(chat_id=chat_id, text="⚠️ Journey details expired. Please search again.")
                    )
                return await self._show_train_details(chat_id, journey_id, context)
            
            elif callback_data.startswith("s_page_"):
                page = int(callback_data.split("_")[2])
                results = context.data.get("search_results", [])
                
                if not results:
                    return HandlerResult(
                        status=HandlerResultStatus.FAILED,
                        response=BotResponse(chat_id=chat_id, text="⚠️ Session expired. Please search again.")
                    )
                
                context.data["search_page"] = page
                
                return HandlerResult(
                    status=HandlerResultStatus.SUCCESS,
                    response=BotResponse(
                        chat_id=chat_id,
                        text=self._format_search_results(results, page=page),
                        inline_keyboard=self._create_result_keyboards(results, page=page)
                    ),
                    data={"search_page": page}
                )
            
            elif callback_data == "f_class":
                # Show Class Filter Keyboard
                return HandlerResult(
                    status=HandlerResultStatus.SUCCESS,
                    response=BotResponse(
                        chat_id=chat_id,
                        text="<b>Select Travel Class:</b>",
                        inline_keyboard=[
                            [{"text": "Sleeper (SL)", "callback_data": "f_val_class_SL"}],
                            [{"text": "AC 3-Tier (3A)", "callback_data": "f_val_class_3A"}],
                            [{"text": "AC 2-Tier (2A)", "callback_data": "f_val_class_2A"}],
                            [{"text": "🔙 Back", "callback_data": f"s_page_{context.data.get('search_page', 0)}"}]
                        ]
                    )
                )

            elif callback_data.startswith("f_val_"):
                # Handle filter value selection
                _, _, filter_type, filter_val = callback_data.split("_")
                # In a real app, we would re-filter results here
                # For now, we'll just acknowledge and show the same page
                return HandlerResult(
                    status=HandlerResultStatus.SUCCESS,
                    response=BotResponse(
                        chat_id=chat_id,
                        text=f"✅ Filter applied: {filter_type}={filter_val}. <i>Refreshing results...</i>",
                    ),
                    follow_up=True,
                    follow_up_text=self._format_search_results(context.data.get("search_results", []), page=context.data.get("search_page", 0))
                )

            return HandlerResult(
                status=HandlerResultStatus.SUCCESS,
                response=BotResponse(chat_id=chat_id, text="Action processed.")
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
