import redis
import json
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import re
import uuid
from datetime import datetime
from difflib import SequenceMatcher
import httpx # Import httpx for making async HTTP requests
from sqlalchemy.orm import Session

from backend.config import Config
from backend.services.cache_service import cache_service
from backend.services.booking_service import BookingService
from backend.api import sos as sos_api
from backend.database import get_db
from backend.models import User
from backend.api.dependencies import get_current_user, get_optional_user

router = APIRouter(prefix="/chat", tags=["chat"])

# Initialize Redis client
# Use Redis when available via CacheService; otherwise keep a local in-memory fallback
_redis = cache_service.redis if cache_service and cache_service.is_available() else None
_local_sessions: Dict[str, Dict[str, Any]] = {}
SESSION_KEY_PREFIX = "chat:session:"

# Pydantic Models for Function Calling (Tools)
class RouteSearchTool(BaseModel):
    """Search for railway routes between a source and destination on a specific date."""
    source: str
    destination: str
    date: Optional[str] = None

class BookRouteTool(BaseModel):
    """Book a railway route for the current user."""
    route_id: str

class SOSAlertTool(BaseModel):
    """Trigger an SOS alert with location and an optional message."""
    location: str
    message: Optional[str] = None

class GatewayValidator:
    """
    Inspects AI-generated tool calls against user permissions before execution.
    """
    def __init__(self, user: Optional[User], db: Session):
        self.user = user
        self.db = db

    def validate_and_execute(self, tool_call: Dict[str, Any]) -> Optional['ChatResponse']:
        function_name = tool_call["function"]["name"]
        try:
            arguments = json.loads(tool_call["function"]["arguments"])
        except json.JSONDecodeError:
            return ChatResponse(reply="I received an invalid tool call from the AI.")

        response_obj = ChatResponse(reply="")

        # Protect sensitive tool calls when user is not authenticated
        if function_name in ("BookRouteTool", "SOSAlertTool") and not self.user:
            response_obj.reply = "You need to sign in to perform this action. Please log in to continue."
            response_obj.state = "auth_required"
            return response_obj

        if function_name == "RouteSearchTool":
            source = arguments.get("source")
            destination = arguments.get("destination")
            date = arguments.get("date")
            reply_text = f"AI requested a route search from {source} to {destination}"
            if date:
                reply_text += f" on {date}"
            response_obj.reply = reply_text + ". I would now perform the search."
            response_obj.trigger_search = True
            response_obj.collected = {"source": source, "destination": destination, "date": date}
            response_obj.actions = [
                ChatAction(label="View Results", type="intent", value="view_search"),
                ChatAction(label="Modify Search", type="intent", value="modify_search")
            ]
            response_obj.state = "search"
            return response_obj

        elif function_name == "BookRouteTool":
            route_id = arguments.get("route_id")
            # The user is booking for themselves, using the authenticated user's ID.
            # In a real scenario, you would call a booking service here.
            # e.g., booking_service = BookingService(self.db)
            # booking_service.create_booking(user_id=self.user.id, route_id=route_id, ...)
            response_obj.reply = f"AI requested to book route {route_id} for you. Booking would proceed."
            response_obj.actions = [ChatAction(label="View Bookings", type="navigate", value="/bookings")]
            response_obj.state = "booking"
            return response_obj

        elif function_name == "SOSAlertTool":
            # For now, allow any authenticated user to trigger SOS.
            # Rate limiting could be added here.
            location = arguments.get("location")
            message = arguments.get("message")
            # In a real scenario, you'd call the SOS service.
            # e.g., await sos_api.trigger_sos_alert(location, message)
            response_obj.reply = f"AI requested an SOS alert from {location} with message: '{message}'. An alert would be triggered."
            response_obj.actions = [ChatAction(label="Open SOS Page", type="navigate", value="/sos")]
            response_obj.state = "sos"
            return response_obj
        
        return None

def _session_key(session_id: str) -> str:
    return f"{SESSION_KEY_PREFIX}{session_id}"


def _load_session(session_id: str) -> Dict[str, Any]:
    if _redis:
        try:
            raw = _redis.get(_session_key(session_id))
            if raw:
                return json.loads(raw)
        except Exception:
            pass
    return _local_sessions.get(session_id, {"created_at": datetime.utcnow().isoformat(), "messages": [], "context": {}})


def _save_session(session_id: str, data: Dict[str, Any]) -> None:
    ttl = Config.REDIS_SESSION_EXPIRY_SECONDS
    if _redis:
        try:
            _redis.set(_session_key(session_id), json.dumps(data), ex=ttl)
            return
        except Exception:
            pass
    _local_sessions[session_id] = data


def _count_active_sessions() -> int:
    if _redis:
        try:
            return sum(1 for _ in _redis.scan_iter(match=f"{SESSION_KEY_PREFIX}*", count=100))
        except Exception:
            return len(_local_sessions)
    return len(_local_sessions)

# City to major station mapping (contains major junction stations for each city)
# TODO: In a production system, this should be loaded from a persistent store or a service.
CITY_STATION_MAP = {
    'delhi': {'code': 'NDLS', 'name': 'New Delhi', 'station_type': 'major_junction'},
    'mumbai': {'code': 'CSTM', 'name': 'Mumbai Central', 'station_type': 'major_junction'},
    'kolkata': {'code': 'KOAA', 'name': 'Kolkata', 'station_type': 'major_junction'},
    'bangalore': {'code': 'SBC', 'name': 'Bangalore City', 'station_type': 'major_junction'},
    'chennai': {'code': 'MAS', 'name': 'Chennai Central', 'station_type': 'major_junction'},
    'hyderabad': {'code': 'SC', 'name': 'Secunderabad', 'station_type': 'major_junction'},
    'pune': {'code': 'PUNE', 'name': 'Pune Junction', 'station_type': 'major_junction'},
    'jaipur': {'code': 'JP', 'name': 'Jaipur Junction', 'station_type': 'major_junction'},
    'ahmedabad': {'code': 'ADI', 'name': 'Ahmedabad Junction', 'station_type': 'major_junction'},
    'lucknow': {'code': 'LKO', 'name': 'Lucknow Junction', 'station_type': 'major_junction'},
    'kota': {'code': 'KOTA', 'name': 'Kota Junction', 'station_type': 'major_junction'},
    'indore': {'code': 'INDB', 'name': 'Indore Junction', 'station_type': 'major_junction'},
    'bhopal': {'code': 'BPL', 'name': 'Bhopal Junction', 'station_type': 'major_junction'},
    'nagpur': {'code': 'NGP', 'name': 'Nagpur Junction', 'station_type': 'major_junction'},
    'goa': {'code': 'VASCO', 'name': 'Vasco da Gama', 'station_type': 'major_junction'},
    'surat': {'code': 'ST', 'name': 'Surat Station', 'station_type': 'major_junction'},
    'vadodara': {'code': 'BRC', 'name': 'Vadodara Junction', 'station_type': 'major_junction'},
    'visakhapatnam': {'code': 'VSKP', 'name': 'Visakhapatnam Junction', 'station_type': 'major_junction'},
    'kochi': {'code': 'EKM', 'name': 'Kochi Junction', 'station_type': 'major_junction'},
    'thiruvananthapuram': {'code': 'TVM', 'name': 'Thiruvananthapuram Central', 'station_type': 'major_junction'},
    'guwahati': {'code': 'GHY', 'name': 'Guwahati Junction', 'station_type': 'major_junction'},
    'chandigarh': {'code': 'CDG', 'name': 'Chandigarh Junction', 'station_type': 'major_junction'},
    'kanpur': {'code': 'CNB', 'name': 'Kanpur Central', 'station_type': 'major_junction'},
    'varanasi': {'code': 'BSB', 'name': 'Varanasi Junction', 'station_type': 'major_junction'},
    'patna': {'code': 'PNBE', 'name': 'Patna Junction', 'station_type': 'major_junction'},
    'ranchi': {'code': 'RNC', 'name': 'Ranchi Junction', 'station_type': 'major_junction'},
    'raipur': {'code': 'R', 'name': 'Raipur Junction', 'station_type': 'major_junction'},
    'jodhpur': {'code': 'JU', 'name': 'Jodhpur Junction', 'station_type': 'major_junction'},
    'udaipur': {'code': 'UDZ', 'name': 'Udaipur City', 'station_type': 'major_junction'},
    'aurangabad': {'code': 'AWB', 'name': 'Aurangabad Station', 'station_type': 'major_junction'},
}

class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = None

class ChatAction(BaseModel):
    label: str
    type: str
    value: Optional[str] = None

class ChatResponse(BaseModel):
    reply: str
    message: Optional[str] = None
    actions: Optional[List[ChatAction]] = None
    state: Optional[str] = "idle"
    trigger_search: Optional[bool] = False
    collected: Optional[Dict[str, str]] = None
    session_id: Optional[str] = None
    correlation_id: Optional[str] = None


async def call_openrouter_api(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calls the OpenRouter API with the given messages and returns the response."""
    if not Config.OPENROUTER_API_KEY:
        raise HTTPException(status_code=500, detail="OpenRouter API key not configured.")

    client = httpx.AsyncClient()
    
    # Define the tools available to the AI
    tools = [
        {
            "type": "function",
            "function": {
                "name": "RouteSearchTool",
                "description": RouteSearchTool.__doc__,
                "parameters": RouteSearchTool.model_json_schema()
            }
        },
        {
            "type": "function",
            "function": {
                "name": "BookRouteTool",
                "description": BookRouteTool.__doc__,
                "parameters": BookRouteTool.model_json_schema()
            }
        },
        {
            "type": "function",
            "function": {
                "name": "SOSAlertTool",
                "description": SOSAlertTool.__doc__,
                "parameters": SOSAlertTool.model_json_schema()
            }
        }
    ]

    try:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {Config.OPENROUTER_API_KEY}",
                "HTTP-Referer": "https://github.com/Gaurav-Nagar-official/startupV2", # Replace with your actual frontend URL
                "X-Title": "RouteMaster-Backend",
            },
            json={
                "model": "openai/gpt-4o",  # Or another suitable model
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto",  # Allow AI to choose whether to use a tool
            },
            timeout=30.0,
        )
        response.raise_for_status()
        return response.json()
    except httpx.HTTPStatusError as e:
        print(f"OpenRouter API HTTP error: {e.response.status_code} - {e.response.text}")
        raise HTTPException(status_code=e.response.status_code, detail=f"OpenRouter API error: {e.response.text}")
    except httpx.RequestError as e:
        print(f"OpenRouter API request error: {e}")
        raise HTTPException(status_code=500, detail=f"OpenRouter API request failed: {e}")
    finally:
        await client.aclose()


def string_similarity(a: str, b: str) -> float:
    """Calculate string similarity ratio (0-1) using SequenceMatcher."""
    return SequenceMatcher(None, a.lower(), b.lower()).ratio()


def resolve_city_to_station(city_name: str) -> Optional[Dict[str, str]]:
    city_lower = city_name.lower().strip()
    if city_lower in CITY_STATION_MAP:
        station_info = CITY_STATION_MAP[city_lower]
        return {"name": station_info["name"], "code": station_info["code"], "city": city_name.title(), "type": "city"}

    best_match = None
    best_similarity = 0.6
    for city, station_info in CITY_STATION_MAP.items():
        similarity = string_similarity(city_lower, city)
        if similarity > best_similarity:
            best_similarity = similarity
            best_match = (city, station_info)
        station_name_lower = station_info["name"].lower()
        similarity = string_similarity(city_lower, station_name_lower)
        if similarity > best_similarity:
            best_similarity = similarity
            best_match = (city, station_info)

    if best_match:
        city, station_info = best_match
        return {"name": station_info["name"], "code": station_info["code"], "city": city.title(), "type": "city"}
    return None


def extract_stations_from_message(message: str) -> Dict[str, str]:
    message_lower = message.lower()
    temp_message = re.sub(r"\s+(?:on|at|in)\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|next\s+monday|next\s+tuesday|next\s+wednesday|next\s+thursday|next\s+saturday|next\s+sunday|next\s+friday|tomorrow|today|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})","",message_lower)
    patterns = [
        r'from\s+([a-z\s]+?)\s+to\s+([a-z\s]+?)(?:\s|$)',
        r'([a-z\s]+?)\s+to\s+([a-z\s]+?)(?:\s|$)',
        r'book\s+(?:from\s+)?([a-z\s]+?)\s+to\s+([a-z\s]+?)(?:\s|$)',
        r'train\s+(?:from\s+)?([a-z\s]+?)\s+to\s+([a-z\s]+?)(?:\s|$)',
        r'route\s+(?:from\s+)?([a-z\s]+?)\s+to\s+([a-z\s]+?)(?:\s|$)',
        r'journey\s+(?:from\s+)?([a-z\s]+?)\s+to\s+([a-z\s]+?)(?:\s|$)',
        r'travel\s+(?:from\s+)?([a-z\s]+?)\s+to\s+([a-z\s]+?)(?:\s|$)'
    ]
    extracted = {}
    for pattern in patterns:
        match = re.search(pattern, temp_message)
        if match:
            source = match.group(1).strip()
            destination = match.group(2).strip()
            cleanup_words = r'\b(from|book|train|route|ticket|search|journey|travel|via)\b'
            source = re.sub(cleanup_words, '', source).strip()
            destination = re.sub(cleanup_words, '', destination).strip()
            source = re.sub(r'\d+', '', source).strip()
            destination = re.sub(r'\d+', '', destination).strip()
            source = ' '.join(source.split()[:3])
            destination = ' '.join(destination.split()[:3])
            if len(source) > 1 and len(destination) > 1:
                extracted = {"source": source, "destination": destination}
                break
    result = {}
    if extracted:
        source_station = resolve_city_to_station(extracted['source'])
        if source_station:
            result['source'] = source_station['name']
            result['source_city'] = source_station['city']
            result['source_code'] = source_station['code']
        else:
            result['source'] = extracted['source'].title()
        dest_station = resolve_city_to_station(extracted['destination'])
        if dest_station:
            result['destination'] = dest_station['name']
            result['destination_city'] = dest_station['city']
            result['destination_code'] = dest_station['code']
        else:
            result['destination'] = extracted['destination'].title()
    return result


def is_weekday(word: str) -> bool:
    weekdays = ['monday', 'tuesday', 'wednesday', 'thursday', 'friday', 'saturday', 'sunday']
    return word.lower() in weekdays


def get_next_weekday(weekday_name: str) -> str:
    from datetime import datetime, timedelta
    weekday_map = {'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6}
    if weekday_name.lower() not in weekday_map:
        return None
    today = datetime.now()
    target_weekday = weekday_map[weekday_name.lower()]
    current_weekday = today.weekday()
    days_ahead = (target_weekday - current_weekday) % 7
    if days_ahead == 0:
        days_ahead = 7
    next_date = today + timedelta(days=days_ahead)
    return next_date.strftime('%Y-%m-%d')


def get_this_weekday(weekday_name: str) -> str:
    from datetime import datetime, timedelta
    weekday_map = {'monday': 0, 'tuesday': 1, 'wednesday': 2, 'thursday': 3, 'friday': 4, 'saturday': 5, 'sunday': 6}
    if weekday_name.lower() not in weekday_map:
        return None
    today = datetime.now()
    target_weekday = weekday_map[weekday_name.lower()]
    current_weekday = today.weekday()
    days_ahead = (target_weekday - current_weekday) % 7
    if days_ahead < 0:
        days_ahead += 7
    next_date = today + timedelta(days=days_ahead)
    return next_date.strftime('%Y-%m-%d')


def extract_date_from_message(message: str) -> Optional[str]:
    from datetime import datetime, timedelta
    import calendar
    message_lower = message.lower()
    date_patterns = [r'(\d{1,2}[-/]\d{1,2}[-/]\d{4})', r'(\d{4}[-/]\d{1,2}[-/]\d{1,2})', r'(\d{1,2}[-/]\d{1,2}[-/]\d{2})', r'(\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{4})', r'(\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{2})']
    for pattern in date_patterns:
        match = re.search(pattern, message_lower)
        if match:
            date_str = match.group(1)
            try:
                if re.match(r'\d{1,2}[-/]\d{1,2}[-/]\d{4}', date_str):
                    parts = re.split(r'[-/]', date_str)
                    if len(parts) == 3:
                        day, month, year = int(parts[0]), int(parts[1]), int(parts[2])
                        return f"{year:04d}-{month:02d}-{day:02d}"
                elif re.match(r'\d{4}[-/]\d{1,2}[-/]\d{1,2}', date_str):
                    parts = re.split(r'[-/]', date_str)
                    if len(parts) == 3:
                        year, month, day = int(parts[0]), int(parts[1]), int(parts[2])
                        return f"{year:04d}-{month:02d}-{day:02d}"
                elif re.match(r'\d{1,2}[-/]\d{1,2}[-/]\d{2}', date_str):
                    parts = re.split(r'[-/]', date_str)
                    if len(parts) == 3:
                        day, month, year = int(parts[0]), int(parts[1]), int(parts[2]) + 2000
                        return f"{year:04d}-{month:02d}-{day:02d}"
                elif re.match(r'\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{4}', date_str):
                    dt = datetime.strptime(date_str, '%d %b %Y')
                    return dt.strftime('%Y-%m-%d')
                elif re.match(r'\d{1,2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)\s+\d{2}', date_str):
                    dt = datetime.strptime(date_str, '%d %b %y')
                    return dt.strftime('%Y-%m-%d')
            except (ValueError, IndexError):
                continue
    next_weekday_match = re.search(r'\b(?:on\s+)?next\s+(\w+)\b', message_lower)
    if next_weekday_match and is_weekday(next_weekday_match.group(1)):
        result = get_next_weekday(next_weekday_match.group(1))
        if result:
            return result
    on_weekday_match = re.search(r'\b(?:on|in)\s+(\w+)\b', message_lower)
    if on_weekday_match and is_weekday(on_weekday_match.group(1)):
        result = get_next_weekday(on_weekday_match.group(1))
        if result:
            return result
    this_weekday_match = re.search(r'\bthis\s+(\w+)\b', message_lower)
    if this_weekday_match and is_weekday(this_weekday_match.group(1)):
        result = get_this_weekday(this_weekday_match.group(1))
        if result:
            return result
    if 'tomorrow' in message_lower:
        return (datetime.now() + timedelta(days=1)).strftime('%Y-%m-%d')
    if 'today' in message_lower:
        return datetime.now().strftime('%Y-%m-%d')
    weekday_match = re.search(r'\b(monday|tuesday|wednesday|thursday|friday|saturday|sunday)\b', message_lower)
    if weekday_match:
        return get_next_weekday(weekday_match.group(1))
    return None


def get_intent_from_message(message: str) -> str:
    message_lower = message.lower()
    if any(word in message_lower for word in ['book', 'search', 'find', 'route', 'train', 'ticket', 'journey', 'travel']):
        return 'search'
    if any(word in message_lower for word in ['dashboard', 'home', 'main', 'analytics', 'stats']):
        return 'navigate_dashboard'
    if any(word in message_lower for word in ['sos', 'emergency', 'help', 'emergency', 'assist']):
        return 'navigate_sos'
    if any(word in message_lower for word in ['booking', 'my booking', 'history', 'past travels']):
        return 'navigate_bookings'
    if any(word in message_lower for word in ['admin', 'administrator', 'manage', 'management']):
        return 'navigate_admin'
    if any(word in message_lower for word in ['telegram', 'bot', 'mini app', 'app']):
        return 'open_telegram'
    if any(word in message_lower for word in ['help', 'what can you do', 'commands', 'options', 'features']):
        return 'help'
    if any(word in message_lower for word in ['cheapest', 'cost', 'price', 'money', 'low cost']):
        return 'sort_cost'
    if any(word in message_lower for word in ['fastest', 'quick', 'duration', 'time', 'speed']):
        return 'sort_duration'
    if any(word in message_lower for word in ['popular', 'famous', 'top', 'best routes']):
        return 'popular_routes'
    if any(word in message_lower for word in ['pay', 'payment', 'buy', 'purchase']):
        return 'payment_help'
    return 'unknown'


def generate_response(intent: str, message: str, session_data: Dict[str, Any]) -> ChatResponse:
    actions = []
    reply = ""
    trigger_search = False
    collected = None
    correlation_id = None
    if intent == 'search':
        stations = extract_stations_from_message(message)
        date = extract_date_from_message(message)
        if stations.get('source') and stations.get('destination'):
            source_display = f"{stations['source']} ({stations.get('source_city', '')})" if stations.get('source_city') else stations['source']
            dest_display = f"{stations['destination']} ({stations.get('destination_city', '')})" if stations.get('destination_city') else stations['destination']
            reply = f"🔍 Searching for routes from {source_display} to {dest_display}"
            if date:
                reply += f" on {date}"
            reply += "..."
            trigger_search = True
            collected = {
                "source": stations.get('source', ''),
                "source_city": stations.get('source_city', ''),
                "source_code": stations.get('source_code', ''),
                "destination": stations.get('destination', ''),
                "destination_city": stations.get('destination_city', ''),
                "destination_code": stations.get('destination_code', ''),
            }
            if date:
                collected["date"] = date
            correlation_id = str(uuid.uuid4())
            actions = [
                ChatAction(label="View Results", type="intent", value="view_search"),
                ChatAction(label="Modify Search", type="intent", value="modify_search"),
                ChatAction(label="Dashboard", type="navigate", value="/dashboard")
            ]
        else:
            reply = "I need both source and destination stations to search for routes.\n\n💡 **Examples:**\n• 'Delhi to Mumbai'\n• 'Book ticket from Kota to Bangalore'\n• 'Kolkata to Chennai on Monday'\n• 'Search trains Jaipur to Pune on 12-02-2026'\n\nPlease try again!"
            actions = [
                ChatAction(label="Popular Routes", type="intent", value="popular_routes"),
                ChatAction(label="Search Form", type="navigate", value="/"),
                ChatAction(label="Help", type="intent", value="help")
            ]
    elif intent == 'navigate_dashboard':
        reply = "📊 Opening your dashboard..."
        actions = [
            ChatAction(label="Go to Dashboard", type="navigate", value="/dashboard")
        ]

    elif intent == 'navigate_sos':
        reply = "🚨 Opening emergency SOS page..."
        actions = [
            ChatAction(label="Open SOS", type="navigate", value="/sos")
        ]

    elif intent == 'navigate_bookings':
        reply = "📋 Opening your bookings..."
        actions = [
            ChatAction(label="View Bookings", type="navigate", value="/bookings")
        ]

    elif intent == 'navigate_admin':
        reply = "⚙️ Opening admin dashboard..."
        actions = [
            ChatAction(label="Admin Panel", type="navigate", value="/admin")
        ]

    elif intent == 'open_telegram':
        reply = "📱 Opening RouteMaster in Telegram..."
        actions = [
            ChatAction(label="Open Telegram Bot", type="open_url", value="https://t.me/RoutemasternagarindustrisBot")
        ]

    elif intent == 'sort_cost':
        reply = "💰 Sorting routes by lowest cost..."
        actions = [
            ChatAction(label="Sort by Cost", type="sort", value="cost")
        ]

    elif intent == 'sort_duration':
        reply = "⚡ Sorting routes by shortest duration..."
        actions = [
            ChatAction(label="Sort by Duration", type="sort", value="duration")
        ]

    elif intent == 'popular_routes':
        reply = "🌟 **Popular Routes in RouteMaster** — try 'Delhi → Mumbai', 'Mumbai → Goa' or 'Bengaluru → Chennai'."

    # Build and return ChatResponse
    return ChatResponse(
        reply=reply or "I'm not sure how to help with that.",
        message=None,
        actions=actions or None,
        state="search" if trigger_search else "idle",
        trigger_search=trigger_search,
        collected=collected,
        session_id=session_data.get("session_id") if isinstance(session_data, dict) else None,
        correlation_id=correlation_id,
    )

# -- POST /chat (uses Redis-backed sessions) --
@router.post("/", response_model=ChatResponse)
async def chat_message(
    request: ChatMessage,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    session_id = request.session_id or str(uuid.uuid4())
    session = _load_session(session_id)

    session.setdefault("messages", []).append({
        "role": "user",
        "content": request.message,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    # --- AI Integration Start ---
    response_obj: ChatResponse
    validator = GatewayValidator(current_user, db)

    # If OpenRouter API key is not configured, fall back to a lightweight rule-based generator
    if not Config.OPENROUTER_API_KEY:
        intent = get_intent_from_message(request.message)
        # If intent is unknown but message contains 'X to Y' station pattern, treat as search
        if intent == 'unknown':
            stations_look = extract_stations_from_message(request.message)
            if stations_look.get('source') and stations_look.get('destination'):
                intent = 'search'

        response_obj = generate_response(intent, request.message, session)
        ai_reply_content = response_obj.reply
        tool_calls = []
    else:
        ai_messages = []
        # Add system message to instruct the AI
        ai_messages.append({
            "role": "system",
            "content": "You are RouteMaster, an AI assistant for railway travel. You can search for routes, book tickets, and trigger SOS alerts. Use the available tools when appropriate."
        })
        # Implement sliding window for chat history
        last_10_messages = session["messages"][-10:]
        for msg in last_10_messages:
            # Ensure only 'user' and 'assistant' roles are sent to the AI
            if msg["role"] in ["user", "assistant"]:
                ai_messages.append({"role": msg["role"], "content": msg["content"]})
        
        try:
            ai_response = await call_openrouter_api(ai_messages)
        except HTTPException:
            # If AI API fails, fall back to local generator
            intent = get_intent_from_message(request.message)
            response_obj = generate_response(intent, request.message, session)
            ai_reply_content = response_obj.reply
            tool_calls = []
        else:
            # Process AI response
            tool_calls = []
            ai_reply_content = ""
            if ai_response and ai_response.get("choices"):
                message_from_ai = ai_response["choices"][0]["message"]
                if message_from_ai.get("content"):
                    ai_reply_content = message_from_ai["content"]
                if message_from_ai.get("tool_calls"):
                    tool_calls = message_from_ai["tool_calls"]

            response_obj = ChatResponse(reply=ai_reply_content or "I'm not sure how to respond to that.")

    # If the response was produced by tools (AI or local generator returned tool-like intent), handle them below
    if 'tool_calls' not in locals():
        tool_calls = []

    if tool_calls:
        for tool_call in tool_calls:
            validated_response = validator.validate_and_execute(tool_call)
            if validated_response:
                response_obj = validated_response

    # --- AI Integration End ---
    
    session["messages"].append({
        "role": "assistant",
        "content": response_obj.reply,
        "actions": [a.dict() for a in (response_obj.actions or [])],
        "timestamp": datetime.utcnow().isoformat()
    })

    _save_session(session_id, session)

    response_obj.session_id = session_id
    response_obj.state = response_obj.state if response_obj.state else "idle"
    return response_obj


@router.get("/health")
async def chat_health():
    redis_ok = False
    try:
        if _redis:
            _redis.ping()
            redis_ok = True
    except Exception:
        redis_ok = False

    return {
        "status": "healthy" if (redis_ok or _local_sessions) else "degraded",
        "service": "chat",
        "redis_ok": redis_ok,
        "sessions_active": _count_active_sessions(),
        "timestamp": datetime.utcnow().isoformat()
    }