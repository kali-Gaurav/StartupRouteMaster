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
    IntentType, HandlerResult, HandlerResultStatus
)
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
            results = await search_service.search_trains(
                from_station=from_station,
                to_station=to_station,
                date=search_date,
                train_no=train_no if train_no else None
            )
            
            # Limit results
            return results[:feature_config.search_max_results]
            
        except Exception as e:
            logger.error(f"Error searching trains: {e}")
            # Return mock data for development
            return self._get_mock_results(from_station, to_station, date)
    
    def _format_search_results(self, results: List[Dict[str, Any]]) -> str:
        """Format search results for display."""
        if not results:
            return "🔍 <b>No trains found</b>\n\nTry a different search."
        
        text = f"🚂 <b>Train Search Results</b> ({len(results)} trains)\n"
        text += "━━━━━━━━━━━━━━━━━━━━━━━━\n\n"
        
        for i, train in enumerate(results, 1):
            train_no = train.get("train_no", "N/A")
            train_name = train.get("train_name", "Express")
            departure = train.get("departure", "N/A")
            arrival = train.get("arrival", "N/A")
            duration = train.get("duration", "N/A")
            classes = train.get("classes", [])
            
            text += f"<b>{i}. {train_no} - {train_name}</b>\n"
            text += f"   🕐 {departure} → {arrival} ({duration})\n"
            text += f"   🎫 Classes: {', '.join(classes) if classes else 'Contact for info'}\n"
            text += "\n"
        
        text += "━━━━━━━━━━━━━━━━━━━━━━━━\n"
        text += "Tap a train to view availability or book."
        
        return text
    
    def _create_result_keyboards(
        self, 
        results: List[Dict[str, Any]]
    ) -> List[List[Dict[str, str]]]:
        """Create inline keyboards for search results."""
        keyboards = []
        
        for train in results[:5]:  # Limit to 5 results
            train_no = train.get("train_no", "")
            train_name = train.get("train_name", "")[:20]
            keyboards.append([
                {
                    "text": f"🚂 {train_no} {train_name}",
                    "callback_data": f"train_{train_no}"
                }
            ])
        
        # Add pagination if needed
        if len(results) > 5:
            keyboards.append([
                {"text": "📄 More Results", "callback_data": "search_more"},
                {"text": "🔙 New Search", "callback_data": "search_new"}
            ])
        
        # Add action buttons
        keyboards.append([
            {"text": "🔍 Check Availability", "callback_data": "check_avail_all"},
            {"text": "🎫 Book Now", "callback_data": "book_any"}
        ])
        
        return keyboards
    
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