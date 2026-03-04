from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import re
import uuid
import asyncio
from datetime import datetime
from difflib import SequenceMatcher
import httpx # Import httpx for making async HTTP requests
import json
from sqlalchemy.orm import Session
import logging

from database.config import Config
from services.cache_service import cache_service
from services.booking_service import BookingService
from api import sos as sos_api
from database import get_db
from database.models import User, Route as RouteModel
from api.dependencies import get_current_user, get_optional_user
from utils.limiter import limiter  # import limiter from its source module
from pybreaker import CircuitBreaker, CircuitBreakerError # New: Import CircuitBreaker
from core.monitoring import CHATBOT_MESSAGES_TOTAL, CHATBOT_ACTION_EXECUTED_TOTAL

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/chat", tags=["chat"])

class MemorySync(BaseModel):
    memory: Dict[str, Any]

@router.get("/memory")
async def get_chat_memory(
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """Get chat memory (session preferences, history).
    
    Unauthenticated users get empty memory; authenticated users get their saved preferences.
    """
    if not current_user or not current_user.profile:
        return {"memory": {}}
    return {"memory": current_user.profile.ai_memory or {}}

@router.post("/memory")
async def update_chat_memory(
    payload: MemorySync,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """Update chat memory (save preferences, search history, etc.).
    
    Unauthenticated users' data is stored locally in browser; authenticated users save to profile.
    """
    if not current_user or not current_user.profile:
        # Anonymous user - return success but don't persist
        # (Frontend will handle local storage)
        return {"status": "success", "memory": payload.memory, "anonymous": True}
    
    current_memory = current_user.profile.ai_memory or {}
    updated_memory = {**current_memory, **payload.memory}
    current_user.profile.ai_memory = updated_memory
    db.commit()
    return {"status": "success", "memory": updated_memory}

# Initialize Redis client
# Use Redis when available via CacheService; otherwise keep a local in-memory fallback
_redis = cache_service.redis if cache_service and cache_service.is_available() else None
_local_sessions: Dict[str, Dict[str, Any]] = {}
SESSION_KEY_PREFIX = "chat:session:"
TOKEN_BUDGET = 4096  # Example token budget

# New: Circuit Breaker for OpenRouter API calls
openrouter_breaker = CircuitBreaker(
    fail_max=Config.OPENROUTER_CIRCUIT_BREAKER_FAILURE_THRESHOLD,
    reset_timeout=Config.OPENROUTER_CIRCUIT_BREAKER_RECOVERY_TIMEOUT,
    exclude=Config.OPENROUTER_CIRCUIT_BREAKER_EXPECTED_EXCEPTIONS
)

# Pydantic Models for Function Calling (Tools)
class RouteSearchTool(BaseModel):
    """Search for railway routes between a source and destination on a specific date."""
    source: str
    destination: str
    date: Optional[str] = None

class MultiModalPlanTool(BaseModel):
    """Plan optimal multi-modal journeys combining train, bus, and flight options with commission bias."""
    source: str
    destination: str
    date: Optional[str] = None
    budget: Optional[str] = None
    preferences: Optional[str] = None

class BookRouteTool(BaseModel):
    """Book a railway route for the current user."""
    route_id: str
    hold_seat: Optional[bool] = False

class SOSAlertTool(BaseModel):
    """Trigger an SOS alert with location and an optional message."""
    location: str
    message: Optional[str] = None

class RailwayDatabaseTool(BaseModel):
    """Query the railway database for train schedules, station info, or platform details.
    Use this to answer factual questions about train timings and station data.
    """
    query_type: str # 'train_schedule', 'station_info', 'platform_details'
    train_number: Optional[str] = None
    station_code: Optional[str] = None

class FareCalculationTool(BaseModel):
    """Calculate the approximate fare between two stations for a given class."""
    source: str
    destination: str
    travel_class: str # 'SL', '3A', '2A', '1A', 'CC'

class GatewayValidator:
    """
    Inspects AI-generated tool calls against user permissions before execution.
    """
    def __init__(self, user: Optional[User], db: Session):
        self.user = user
        self.db = db

    async def validate_and_execute(self, tool_call: Dict[str, Any]) -> Optional['ChatResponse']:
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
            from database.session import SessionTransit
            transit_db = SessionTransit()
            try:
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
                
                # perform actual search using route engine + helpers
                try:
                    from core.route_engine import route_engine
                    from core.route_engine.constraints import RouteConstraints
                    from utils.station_utils import resolve_stations
                    from utils.validation import validate_date_string
                    from datetime import datetime

                    travel_dt = None
                    if date:
                        travel_dt = validate_date_string(date, allow_past=False)
                    if not travel_dt:
                        travel_dt = datetime.utcnow()

                    src_stop, dst_stop = resolve_stations(transit_db, source, destination)
                    if src_stop and dst_stop:
                        # Apply modern optimized constraints
                        constraints = RouteConstraints(max_transfers=3, range_minutes=1440)
                        routes = await route_engine.search_routes(src_stop.code, dst_stop.code, travel_dt, constraints=constraints)
                        # convert routes to dict form
                        routes_data = []
                        for route in routes:
                            routes_data.append({
                                'segments': [
                                    {k: getattr(seg, k) for k in ['trip_id','departure_stop_id','arrival_stop_id','departure_time','arrival_time','duration_minutes','distance_km','fare','train_name','train_number']}
                                    for seg in route.segments
                                ],
                                'transfers': [
                                    {k: getattr(t, k) for k in ['station_id','arrival_time','departure_time','duration_minutes','station_name','facilities_score','safety_score']}
                                    for t in route.transfers
                                ],
                                'total_duration': route.total_duration,
                                'total_distance': route.total_distance,
                                'total_cost': getattr(route, 'total_cost', 0), # FIXED: was total_fare
                                'score': getattr(route, 'score', None)
                            })
                        response_obj.search_results = routes_data
                    else:
                        response_obj.reply += " However I could not resolve the station names for the search."
                except Exception as e:
                    logger.error(f"RouteSearchTool execution failed: {e}")
                return response_obj
            finally:
                transit_db.close()

        elif function_name == "RailwayDatabaseTool":
            from database.session import SessionTransit
            transit_db = SessionTransit()
            try:
                query_type = arguments.get("query_type")
                train_number = arguments.get("train_number")
                station_code = arguments.get("station_code")
                
                if query_type == "train_schedule" and train_number:
                    from database.models import StopTime, Stop, Trip, Route
                    results = transit_db.query(StopTime, Stop.name, Stop.code)\
                        .join(Stop, StopTime.stop_id == Stop.id)\
                        .join(Trip, StopTime.trip_id == Trip.id)\
                        .join(Route, Trip.route_id == Route.id)\
                        .filter(Route.route_id == train_number)\
                        .order_by(StopTime.stop_sequence).all()
                    
                    if not results:
                        response_obj.reply = f"I couldn't find any schedule information for train {train_number}."
                    else:
                        sched_list = [f"{r[2]} ({r[1]}): {r[0].arrival_time}" for r in results]
                        response_obj.reply = f"Schedule for {train_number}:\n" + "\n".join(sched_list[:10]) + ("\n..." if len(sched_list) > 10 else "")
                    return response_obj

                elif query_type == "station_info" and station_code:
                    from database.models import Stop
                    stop = transit_db.query(Stop).filter(Stop.code == station_code.upper()).first()
                    if stop:
                        response_obj.reply = f"Station: {stop.name} ({stop.code})\nLocation: {stop.latitude}, {stop.longitude}\nPlatforms: {stop.platform_count or 'Unknown'}"
                    else:
                        response_obj.reply = f"I couldn't find details for station {station_code}."
                    return response_obj
            finally:
                transit_db.close()

        elif function_name == "FareCalculationTool":
            from database.session import SessionTransit
            from utils.fare_calculator import FareCalculator
            from utils.station_utils import resolve_stations
            import math
            
            transit_db = SessionTransit()
            try:
                source = arguments.get("source")
                destination = arguments.get("destination")
                travel_class = arguments.get("travel_class", "SL")
                
                src_stop, dst_stop = resolve_stations(transit_db, source, destination)
                if src_stop and dst_stop:
                    # Calculate Haversine Distance (approximate)
                    def haversine(lat1, lon1, lat2, lon2):
                        R = 6371 # Earth radius in km
                        dlat = math.radians(lat2 - lat1)
                        dlon = math.radians(lon2 - lon1)
                        a = math.sin(dlat/2)**2 + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon/2)**2
                        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))
                        return R * c

                    dist = haversine(src_stop.latitude, src_stop.longitude, dst_stop.latitude, dst_stop.longitude)
                    # Train tracks are longer than birds-eye distance (~20% more)
                    dist = dist * 1.2 
                    
                    fare = FareCalculator.calculate(dist, travel_class)
                    response_obj.reply = f"The estimated fare for **{travel_class}** from **{src_stop.name}** to **{dst_stop.name}** is **₹{fare}**."
                    response_obj.actions = [ChatAction(label="Book Now", type="navigate", value=f"/?from={src_stop.code}&to={dst_stop.code}", icon="Ticket")]
                else:
                    response_obj.reply = f"I couldn't calculate the fare because I couldn't find the stations {source} or {destination}."
                return response_obj
            finally:
                transit_db.close()

        elif function_name == "MultiModalPlanTool":
            source = arguments.get("source")
            destination = arguments.get("destination")
            date = arguments.get("date")
            budget = arguments.get("budget")
            preferences = arguments.get("preferences")

            plan_description = f"multi-modal journey from {source} to {destination}"
            if date:
                plan_description += f" on {date}"
            if budget:
                plan_description += f" with {budget} budget"
            if preferences:
                plan_description += f" considering {preferences}"

            response_obj.reply = f"AI is planning an optimal {plan_description}. I'll analyze train, bus, and flight combinations to find the best options with commission-earning partners."
            response_obj.trigger_search = True
            response_obj.collected = {
                "source": source,
                "destination": destination,
                "date": date,
                "budget": budget,
                "preferences": preferences,
                "multi_modal": True
            }
            response_obj.actions = [
                ChatAction(label="View Multi-Modal Options", type="intent", value="view_multimodal"),
                ChatAction(label="Adjust Preferences", type="intent", value="modify_plan")
            ]
            response_obj.state = "multimodal_plan"
            return response_obj

        elif function_name == "BookRouteTool":
            route_id = arguments.get("route_id")
            hold_seat = arguments.get("hold_seat", False)
            
            booking_service = BookingService(self.db)
            route = self.db.query(RouteModel).filter(RouteModel.id == route_id).first()

            if not route:
                response_obj.reply = f"Could not find route with ID {route_id}."
                return response_obj

            if hold_seat:
                if not self.user:
                    response_obj.reply = "You need to sign in to hold a seat. Please log in to continue."
                    response_obj.state = "auth_required"
                    return response_obj
                
                # Assuming a default amount or extracting from route for hold
                amount_for_hold = route.total_cost if route.total_cost else 0.0
                booking_details = route.segments # or a summary of segments

                held_booking = booking_service.hold_seat(
                    user_id=self.user.id,
                    route_id=route_id,
                    travel_date="2026-02-14", # Placeholder, ideally derived from context or tool
                    booking_details=booking_details,
                    amount_paid=amount_for_hold
                )
                if held_booking:
                    response_obj.reply = f"AI has held a seat for you on route {route_id}. Your pending booking ID is {held_booking.id}. Please proceed to payment to confirm."
                    response_obj.actions = [ChatAction(label="Complete Booking", type="navigate", value=f"/bookings/{held_booking.id}/payment")]
                    response_obj.state = "booking_pending"
                else:
                    response_obj.reply = f"Failed to hold a seat on route {route_id}."
                return response_obj
            else:
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


def _load_session(session_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
    session_data = {
        "created_at": datetime.utcnow().isoformat(), 
        "messages": [], 
        "context": {},
        "extracted_entities": {}
    }

    # 1. Try Redis First
    if _redis:
        try:
            raw = _redis.get(_session_key(session_id))
            if raw:
                session_data = json.loads(raw)
        except Exception:
            pass
    elif session_id in _local_sessions:
        session_data = _local_sessions[session_id]

    # 2. Layer in Persistent AI Memory from Database
    if user_id:
        from database.session import SessionLocal
        from database.models import Profile
        db = SessionLocal()
        try:
            profile = db.query(Profile).filter(Profile.user_id == user_id).first()
            if profile and profile.ai_memory:
                # Merge persistent preferences/facts into current context
                session_data.setdefault("context", {}).update(profile.ai_memory)
        finally:
            db.close()

    return session_data


def _save_session(session_id: str, data: Dict[str, Any]) -> None:
    """
    Saves session with a strict 10-message window and persistent entities.
    """
    ttl = Config.REDIS_SESSION_EXPIRY_SECONDS
    
    # 1. Enforce 10-message context window (5 user + 5 assistant)
    messages = data.get("messages", [])
    if len(messages) > 10:
        messages = messages[-10:]
    
    # 2. Extract and Persist Entities (Source, Destination, Date)
    entities = data.get("extracted_entities", {})
    
    # Also look into recent messages if not explicitly set
    for msg in reversed(messages):
        if msg.get("role") == "assistant" and msg.get("collected"):
            for k, v in msg["collected"].items():
                if v and not entities.get(k):
                    entities[k] = v

    compact_data = {
        "created_at": data.get("created_at"),
        "messages": messages,
        "extracted_entities": entities,
        "context": data.get("context", {})
    }

    if _redis:
        try:
            _redis.set(_session_key(session_id), json.dumps(compact_data), ex=ttl)
            return
        except Exception as e:
            logger.error(f"Failed to save session to Redis: {e}")
            
    # Fallback to local session storage
    _local_sessions[session_id] = compact_data



def _count_active_sessions() -> int:
    if _redis:
        try:
            return sum(1 for _ in _redis.scan_iter(match=f"{SESSION_KEY_PREFIX}*", count=100))
        except Exception:
            return len(_local_sessions)
    return len(_local_sessions)

def count_tokens(text: str) -> int:
    """A simple approximation for token counting."""
    return len(text) // 4

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
    message_id: Optional[str] = None # Added for deduplication

class ChatAction(BaseModel):
    label: str
    type: str
    value: Optional[str] = None
    icon: Optional[str] = None # Added for UI enrichment

class ChatResponse(BaseModel):
    reply: str
    message: Optional[str] = None
    actions: Optional[List[ChatAction]] = None
    suggestions: Optional[List[ChatAction]] = None # Same model for chips
    state: Optional[str] = "idle"
    trigger_search: Optional[bool] = False
    collected: Optional[Dict[str, str]] = None
    session_id: Optional[str] = None
    correlation_id: Optional[str] = None
    # when a route search is executed by the chat gateway, results are placed here
    search_results: Optional[List[Dict[str, Any]]] = None
    intent: Optional[str] = None # Added for decision engine
    confidence: Optional[float] = 1.0 # 0.0 to 1.0

def calculate_confidence(intent: str, message: str) -> float:
    """Heuristic confidence scoring for rule-based engine."""
    base = 0.7
    msg = message.lower()
    
    if intent == 'trigger_sos':
        if any(w in msg for w in ['help', 'danger', 'save', 'panic']):
            base += 0.2
    
    if intent == 'search':
        if 'from' in msg and 'to' in msg:
            base += 0.2
            
    return min(base, 0.99)


@openrouter_breaker # New: Apply circuit breaker
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
                "name": "MultiModalPlanTool",
                "description": MultiModalPlanTool.__doc__,
                "parameters": MultiModalPlanTool.model_json_schema()
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
        },
        {
            "type": "function",
            "function": {
                "name": "FareCalculationTool",
                "description": FareCalculationTool.__doc__,
                "parameters": FareCalculationTool.model_json_schema()
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
                "models": ["openai/gpt-4o", "google/gemini-pro-1.5", "anthropic/claude-3.5-sonnet"],
                "route": "fallback",
                "messages": messages,
                "tools": tools,
                "tool_choice": "auto",  # Allow AI to choose whether to use a tool
                "max_tokens": 1000,
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
    """
    Extracts and resolves stations from user messages using the high-performance
    StationSearchEngine. Handles 'from X to Y' patterns and standalone station names.
    """
    from services.station_search_service import station_search_engine
    
    message_lower = message.lower()
    # Remove common filler words to isolate potential station names
    temp_message = re.sub(r"\s+(?:on|at|in|for|of|with|by)\s+(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|next\s+monday|next\s+tuesday|next\s+wednesday|next\s+thursday|next\s+saturday|next\s+sunday|next\s+friday|tomorrow|today|\d{1,2}[-/]\d{1,2}[-/]\d{2,4})","",message_lower)
    
    patterns = [
        r'from\s+([a-z\s]+?)\s+to\s+([a-z\s]+?)(?:\s|$)',
        r'([a-z\s]+?)\s+to\s+([a-z\s]+?)(?:\s|$)',
        r'book\s+(?:from\s+)?([a-z\s]+?)\s+to\s+([a-z\s]+?)(?:\s|$)',
        r'train\s+(?:from\s+)?([a-z\s]+?)\s+to\s+([a-z\s]+?)(?:\s|$)',
        r'route\s+(?:from\s+)?([a-z\s]+?)\s+to\s+([a-z\s]+?)(?:\s|$)',
    ]
    
    extracted = {}
    for pattern in patterns:
        match = re.search(pattern, temp_message)
        if match:
            source_raw = match.group(1).strip()
            dest_raw = match.group(2).strip()
            
            # Use the Ultra-Fast Engine to resolve these raw strings
            src_res = station_search_engine.resolve(source_raw)
            dst_res = station_search_engine.resolve(dest_raw)
            
            if src_res and dst_res:
                return {
                    "source": src_res.name,
                    "source_city": src_res.city,
                    "source_code": src_res.code,
                    "destination": dst_res.name,
                    "destination_city": dst_res.city,
                    "destination_code": dst_res.code
                }
    
    return {}


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
    # High priority safety intelligence layer
    if any(word in message_lower for word in ['sos', 'panic', 'save', 'emergency', 'unsafe', 'help me', 'danger', 'scared', 'creep']):
        return 'trigger_sos'
    if any(word in message_lower for word in ['guardian', 'family', 'track', 'live', 'telemetry']):
        return 'navigate_guardian'
    if any(word in message_lower for word in ['safe', 'security', 'reliable', 'women']):
        return 'safety_info'
    if any(word in message_lower for word in ['book', 'search', 'find', 'route', 'train', 'ticket', 'journey', 'travel']):
        return 'search'
    if any(word in message_lower for word in ['dashboard', 'home', 'main', 'analytics', 'stats']):
        return 'navigate_dashboard'
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
    suggestions = []
    reply = ""
    trigger_search = False
    collected = None
    correlation_id = None
    
    if intent == 'search':
        # Use existing extracted entities if available
        entities = session_data.get("extracted_entities", {})
        source = entities.get("source")
        destination = entities.get("destination")
        date = entities.get("date")
        
        if source and destination:
            reply = f"🔍 Searching for routes from {source} to {destination}"
            if date:
                reply += f" on {date}"
            reply += "..."
            trigger_search = True
            collected = entities
            correlation_id = str(uuid.uuid4())
            suggestions = [
                ChatAction(label="View Results", type="intent", value="view_search", icon="Eye"),
                ChatAction(label="Modify Search", type="intent", value="modify_search", icon="Edit"),
                ChatAction(label="Dashboard", type="navigate", value="/dashboard", icon="Layout")
            ]
        else:
            reply = """I need both source and destination stations to search for routes.

💡 **Examples:**
• 'Delhi to Mumbai'
• 'Book ticket from Kota to Bangalore'

Please try again!"""
            suggestions = [
                ChatAction(label="Popular Routes", type="intent", value="popular_routes", icon="Star"),
                ChatAction(label="Search Form", type="navigate", value="/", icon="Search"),
                ChatAction(label="Help", type="intent", value="help", icon="HelpCircle")
            ]
    elif intent == 'trigger_sos':
        reply = "🚨 **EMERGENCY MODE**\n\nI can trigger an immediate SOS alert with your live location. Please confirm by tapping the button below."
        suggestions = [
            ChatAction(label="🚨 TRIGGER SOS NOW", type="navigate", value="/sos", icon="AlertTriangle"),
            ChatAction(label="Safe Routes", type="navigate", value="/safety", icon="ShieldCheck")
        ]

    elif intent == 'safety_info':
        reply = "✅ **Route Safety**\n\nRouteMaster uses AI to calculate **Safety Scores** for every route based on historical data and live telemetry."
        suggestions = [
            ChatAction(label="Safety Score Details", type="navigate", value="/safety", icon="Shield"),
            ChatAction(label="Plan Safe Journey", type="navigate", value="/", icon="Map")
        ]

    elif intent == 'popular_routes':
        reply = "🌟 **Popular Routes** — try 'Delhi → Mumbai' or 'Mumbai → Goa'."
        suggestions = [
            ChatAction(label="NDLS → CSTM", type="intent", value="search_ndls_cstm", icon="TrendingUp"),
            ChatAction(label="BCT → ADI", type="intent", value="search_bct_adi", icon="Zap")
        ]

    elif intent == 'pnr_status':
        pnr = session_data.get("extracted_entities", {}).get("pnr")
        if pnr:
            reply = f"🎫 **PNR Status for {pnr}**\n\nI am fetching the latest seat and delay info for your journey. One moment..."
            suggestions = [
                ChatAction(label="Track Live Train", type="navigate", value=f"/live?pnr={pnr}", icon="Navigation"),
                ChatAction(label="Coach Position", type="intent", value=f"coach_pos_{pnr}", icon="MapPin"),
                ChatAction(label="Refresh Status", type="intent", value=f"pnr_{pnr}", icon="RefreshCcw")
            ]
        else:
            reply = "Please provide your **10-digit PNR number** so I can check the status for you."
            suggestions = [
                ChatAction(label="What is PNR?", type="intent", value="pnr_help", icon="HelpCircle")
            ]

    elif intent == 'fallback' or intent == 'unknown':
        reply = """I'm having a little trouble connecting to my full 'AI brain' right now, but I can still help you with the essentials!

• To **Search Trains**, type 'Delhi to Mumbai'
• To **Check PNR**, paste your 10-digit number
• For **Emergencies**, type 'SOS'"""
        suggestions = [
            ChatAction(label="Manual Search", type="navigate", value="/", icon="Search"),
            ChatAction(label="Emergency SOS", type="navigate", value="/sos", icon="AlertTriangle"),
            ChatAction(label="My Bookings", type="navigate", value="/bookings", icon="Ticket")
        ]

    # Build and return ChatResponse
    return ChatResponse(
        reply=reply or "I'm not sure how to help with that.",
        suggestions=suggestions or None,
        state="search" if trigger_search else "idle",
        trigger_search=trigger_search,
        collected=collected,
        session_id=session_data.get("session_id") if isinstance(session_data, dict) else None,
        correlation_id=correlation_id,
        intent=intent,
        confidence=calculate_confidence(intent, message)
    )

# -- POST /chat (uses Redis-backed sessions) --
@router.post("", response_model=ChatResponse)
@limiter.limit("10/minute") # New: Add rate limiting to the chat endpoint
async def chat_message(
    request: Request, # Add Request dependency
    chat_message_request: ChatMessage, # Rename request to chat_message_request
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    # 0. Safety Firewall (CRITICAL)
    from utils.safety import SafetyScanner
    if not SafetyScanner.is_safe(chat_message_request.message):
        raise HTTPException(
            status_code=400, 
            detail="Your message was flagged by our security filters. Please stick to travel-related queries."
        )

    session_id = chat_message_request.session_id or str(uuid.uuid4())
    session = _load_session(session_id)

    # 0. Deduplication Check (Offline Sync Support)
    if chat_message_request.message_id:
        for msg in reversed(session.get("messages", [])):
            if msg.get("message_id") == chat_message_request.message_id:
                logger.info(f"Duplicate message detected: {chat_message_request.message_id}")
                # Return the existing assistant response if found
                # (Simplification: return a flag or the actual cached response)
                return ChatResponse(
                    reply="I already received this message. Processing...",
                    state="duplicate"
                )

    session.setdefault("messages", []).append({
        "role": "user",
        "content": chat_message_request.message,
        "message_id": chat_message_request.message_id,
        "timestamp": datetime.utcnow().isoformat()
    })
    
    # --- AI Integration Start ---
    from utils.translator import MultiLingualBridge
    
    # 1. Detect and Translate to English for Processing
    original_message = chat_message_request.message
    message_en, user_lang = MultiLingualBridge.detect_and_translate(original_message)
    
    # Analyze Sentiment
    from utils.sentiment import SentimentAnalyzer
    sentiment = SentimentAnalyzer.analyze(message_en)
    persona_override = SentimentAnalyzer.get_persona_override(sentiment)
    
    session.setdefault("context", {})["user_language"] = user_lang
    session["context"]["last_sentiment"] = sentiment

    response_obj: ChatResponse
    validator = GatewayValidator(current_user, db)

    # Upgrade 1: Deterministic Intent First (CRITICAL)
    # Use translated English message for extraction
    from utils.nlp_router import get_local_intent
    from utils.entity_extractor import EntityExtractor
    
    extracted = EntityExtractor.extract_all(message_en)
    if extracted:
        session.setdefault("extracted_entities", {}).update(extracted)

    local_intent_data = await asyncio.to_thread(get_local_intent, message_en)
    
    intent = "unknown"
    if local_intent_data:
        intent = local_intent_data["intent"]

    # Fallback to search intent if stations were found
    if intent == 'unknown' and "source" in session["extracted_entities"] and "destination" in session["extracted_entities"]:
        intent = 'search'

    # Fast-Path Execution
    if intent != 'unknown' or not Config.OPENROUTER_API_KEY:
        response_obj = await asyncio.to_thread(generate_response, intent, message_en, session)
        ai_reply_content = response_obj.reply
        tool_calls = []
    else:
        # LLM processing with message_en...
        from utils.token_limiter import TokenLimiter
        from utils.chat_cache import ChatCache
        
        # 1. Check Token Limit
        if not TokenLimiter.check_limit(session_id):
            return ChatResponse(
                reply="You have reached your daily limit for AI messages. Please try again in 24 hours or upgrade to a premium plan.",
                state="limit_exceeded"
            )

        # 2. Check Frequent Questions Cache
        cached_response = ChatCache.get(message_en)
        if cached_response:
            return ChatResponse(**cached_response)

        # Upgrade 2: Structured Tool Calling for complex queries
        ai_messages = []
        ai_messages.append({
            "role": "system",
            "content": f"""{persona_override}

You are Diksha (RouteMaster's AI Brain), an infinitely powerful, omniscient, and highly empathetic multi-modal travel and safety assistant. You have access to vast knowledge about Indian Railways, flights, buses, safety telemetry, and journey planning.

CORE PRINCIPLES:
- Deep Comprehension: Understand complex queries, misspellings, multi-intent requests, and emotional nuances effortlessly.
- Omniscient Routing: Suggest Pareto-optimal combinations of transport (time vs cost vs comfort vs safety) for any route globally or domestically.
- User-Centric & Safe: Always prioritize user safety. Recommend Guardian Mode or SOS if distress is detected. 
- Empowering & Comprehensive: Explain ticketing logic (RAC/WL confirmation chances), refund rules, baggage allowances, and platform guidance expertly.
- Commission & Business: Intelligently prioritize partners (RailYatri, RedBus, MakeMyTrip) that offer highest reliability and commissions naturally.

AVAILABLE MODES:
- Trains: Railway routes (primary focus, deepest expertise, IRCTC logic).
- Buses: Inter-city bus routes (RedBus, AbhiBus).
- Flights: Air routes (MakeMyTrip, Goibibo).
- Cabs/Auto: Last-mile connectivity.

TOOLS USAGE & CAPABILITIES:
- RouteSearchTool: For fast/direct train queries.
- MultiModalPlanTool: For complex cross-country journeys with layovers or budget constraints.
- BookRouteTool: Trigger booking flows.
- SOSAlertTool: Trigger distress signals.
- RailwayDatabaseTool: Query factual railway data (timings, stations).
- FareCalculationTool: Quote accurate ticket prices.
- Always explain your reasoning step-by-step for complex planning. Anticipate the user's next question.

RESPONSE STYLE:
- Highly conversational, intelligent, empathetic, and definitive.
- Use markdown formatting effectively (bullet points, bold text).
- Act as if you have infinite potential to solve any travel or transit problem."""
        })
        
        # Upgrade 3: Conversation Memory Model
        # Token-budgeted context retention
        total_tokens = count_tokens(ai_messages[0]["content"])
        
        temp_messages = []
        for msg in reversed(session["messages"]):
            msg_tokens = count_tokens(msg["content"])
            if total_tokens + msg_tokens > TOKEN_BUDGET:
                break
            temp_messages.insert(0, msg)
            total_tokens += msg_tokens
            
        for msg in temp_messages:
            if msg["role"] in ["user", "assistant"]:
                ai_messages.append({"role": msg["role"], "content": msg["content"]})
        
        try:
            ai_response = await call_openrouter_api(ai_messages)
            
            tool_calls = []
            ai_reply_content = ""
            if ai_response and ai_response.get("choices"):
                message_from_ai = ai_response["choices"][0]["message"]
                if message_from_ai.get("content"):
                    ai_reply_content = message_from_ai["content"]
                if message_from_ai.get("tool_calls"):
                    tool_calls = message_from_ai["tool_calls"]

            response_obj = ChatResponse(
                reply=ai_reply_content or "I'm not sure how to respond to that.",
                intent="llm_fallback",
                confidence=0.5
            )
        except HTTPException as e:
            logger.warning(f"OpenRouter API failed, falling back to local: {e}")
            response_obj = await asyncio.to_thread(generate_response, 'unknown', chat_message_request.message, session)
            ai_reply_content = response_obj.reply
            tool_calls = []

    # If the response was produced by tools (AI or local generator returned tool-like intent), handle them below
    if 'tool_calls' not in locals():
        tool_calls = []

    if tool_calls:
        for tool_call in tool_calls:
            # validator may now be async
            validated_response = await validator.validate_and_execute(tool_call)
            if validated_response:
                response_obj = validated_response

    # --- AI Integration End ---
    
    # Populate cache for frequent questions (if appropriate)
    if intent == "unknown" and response_obj.reply:
        ChatCache.set(message_en, response_obj.dict())

    # Final Translation Step: Translate back to user's native language if not English
    if user_lang != "en":
        response_obj.reply = MultiLingualBridge.translate_to(response_obj.reply, user_lang)

    session["messages"].append({
        "role": "assistant",
        "content": response_obj.reply,
        "actions": [a.dict() for a in (response_obj.actions or [])],
        "timestamp": datetime.utcnow().isoformat()
    })

    _save_session(session_id, session)

    # Track Chatbot Engagement Telemetry
    CHATBOT_MESSAGES_TOTAL.labels(intent=response_obj.state or "idle").inc()

    response_obj.session_id = session_id
    response_obj.state = response_obj.state if response_obj.state else "idle"
    response_obj.message = response_obj.reply
    return response_obj


class ChatFeedback(BaseModel):
    session_id: str
    message_id: Optional[str] = None
    prompt: str
    response: str
    rating: int # 1 for up, -1 for down

@router.post("/feedback")
async def chat_feedback(
    feedback: ChatFeedback,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_optional_user),
):
    """Logs user feedback for AI responses."""
    from database.models import RLFeedbackLog
    try:
        log = RLFeedbackLog(
            user_id=current_user.id if current_user else None,
            prompt=feedback.prompt,
            response=feedback.response,
            rating=feedback.rating,
            timestamp=datetime.utcnow()
        )
        db.add(log)
        db.commit()
        return {"status": "success", "message": "Feedback recorded. Thank you!"}
    except Exception as e:
        logger.error(f"Feedback submission failed: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/history")
async def get_chat_history(
    session_id: str,
    current_user: Optional[User] = Depends(get_optional_user),
):
    """Retrieves conversation history for a given session."""
    session = _load_session(session_id)
    return {
        "session_id": session_id,
        "messages": session.get("messages", []),
        "extracted_entities": session.get("extracted_entities", {})
    }

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
