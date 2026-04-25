from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from typing import List, Optional, Dict, Any
import re
import uuid
import asyncio
import time
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
from database.models import User, Route as RouteModel, PersistentChatMessage, AIIntentLog
from api.dependencies import get_current_user, get_optional_user
from utils.limiter import limiter  # import limiter from its source module
from pybreaker import CircuitBreaker, CircuitBreakerError # New: Import CircuitBreaker
from core.monitoring import CHATBOT_MESSAGES_TOTAL, CHATBOT_ACTION_EXECUTED_TOTAL

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/chat", tags=["chat"])

class MemorySync(BaseModel):
    memory: Dict[str, Any]

@router.get("/memory")
async def get_chat_memory(
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """Get chat memory (session preferences, history)."""
    if not current_user or not current_user.profile:
        return {"memory": {}}
    return {"memory": current_user.profile.ai_memory or {}}

@router.post("/memory")
async def update_chat_memory(
    payload: MemorySync,
    current_user: Optional[User] = Depends(get_optional_user),
    db: Session = Depends(get_db)
):
    """Update chat memory (save preferences, search history, etc.)."""
    if not current_user or not current_user.profile:
        return {"status": "success", "memory": payload.memory, "anonymous": True}
    
    current_memory = current_user.profile.ai_memory or {}
    updated_memory = {**current_memory, **payload.memory}
    current_user.profile.ai_memory = updated_memory
    db.commit()
    return {"status": "success", "memory": updated_memory}

_redis = cache_service.redis if cache_service and cache_service.is_available() else None
_local_sessions: Dict[str, Dict[str, Any]] = {}
SESSION_KEY_PREFIX = "chat:session:"
TOKEN_BUDGET = 4096

openrouter_breaker = CircuitBreaker(
    fail_max=Config.OPENROUTER_CIRCUIT_BREAKER_FAILURE_THRESHOLD,
    reset_timeout=Config.OPENROUTER_CIRCUIT_BREAKER_RECOVERY_TIMEOUT,
    exclude=Config.OPENROUTER_CIRCUIT_BREAKER_EXPECTED_EXCEPTIONS
)

class ChatMessage(BaseModel):
    message: str
    session_id: Optional[str] = None
    message_id: Optional[str] = None

class ChatAction(BaseModel):
    label: str
    type: str
    value: Optional[str] = None
    icon: Optional[str] = None

class ChatResponse(BaseModel):
    reply: str
    message: Optional[str] = None
    actions: Optional[List[ChatAction]] = None
    suggestions: Optional[List[ChatAction]] = None
    state: Optional[str] = "idle"
    trigger_search: Optional[bool] = False
    collected: Optional[Dict[str, str]] = None
    session_id: Optional[str] = None
    correlation_id: Optional[str] = None
    search_results: Optional[List[Dict[str, Any]]] = None
    intent: Optional[str] = None
    confidence: Optional[float] = 1.0

def calculate_confidence(intent: str, message: str) -> float:
    base = 0.7
    msg = message.lower()
    if intent == 'trigger_sos' and any(w in msg for w in ['help', 'danger', 'panic']): base += 0.2
    return min(base, 0.99)

def _session_key(session_id: str) -> str: return f"{SESSION_KEY_PREFIX}{session_id}"

def _get_redis():
    from services.cache_service import cache_service
    return cache_service.redis if cache_service and cache_service.is_available() else None

def _load_session(session_id: str, user_id: Optional[str] = None) -> Dict[str, Any]:
    session_data = {"created_at": datetime.utcnow().isoformat(), "messages": [], "context": {}, "extracted_entities": {}}
    redis_client = _get_redis()
    if redis_client:
        try:
            raw = redis_client.get(_session_key(session_id))
            if raw:
                raw_payload = raw.decode("utf-8") if isinstance(raw, (bytes, bytearray)) else raw
                # Only pass to json.loads if it's a str, bytes, or bytearray
                if isinstance(raw_payload, (str, bytes, bytearray)):
                    session_data = json.loads(raw_payload)
                    return session_data
        except Exception as e:
            logger.warning(f"Redis session load failed: {e}")
    
    if session_id in _local_sessions:
        session_data = _local_sessions[session_id]
    return session_data

def _save_session(session_id: str, data: Dict[str, Any]) -> None:
    ttl = Config.REDIS_SESSION_EXPIRY_SECONDS
    messages = data.get("messages", [])
    if len(messages) > 20: messages = messages[-20:] # Increased history
    
    compact_data = {
        "created_at": data.get("created_at"), 
        "messages": messages, 
        "extracted_entities": data.get("extracted_entities", {}), 
        "context": data.get("context", {})
    }
    
    redis_client = _get_redis()
    if redis_client:
        try: 
            redis_client.set(_session_key(session_id), json.dumps(compact_data), ex=ttl)
        except Exception as e:
            logger.warning(f"Redis session save failed: {e}")
            
    _local_sessions[session_id] = compact_data

@openrouter_breaker
async def call_openrouter_api(messages: List[Dict[str, Any]]) -> Dict[str, Any]:
    if not Config.OPENROUTER_API_KEY: raise HTTPException(status_code=500, detail="API key missing")
    async with httpx.AsyncClient() as client:
        response = await client.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={"Authorization": f"Bearer {Config.OPENROUTER_API_KEY}"},
            json={"models": ["openai/gpt-4o"], "messages": messages},
            timeout=30.0
        )
        return response.json()

def generate_response(intent: str, message: str, session_data: Dict[str, Any], entities: Optional[Dict[str, Any]] = None) -> ChatResponse:
    reply = f"Detected intent: {intent}. How can I help?"
    actions = []
    entities = entities or {}
    
    # Task 2.4: Contextual Entity Merging
    session_entities = session_data.get("extracted_entities", {})
    merged_entities = {**session_entities, **entities}
    
    if intent == 'search': 
        source = merged_entities.get("source")
        dest = merged_entities.get("destination")
        source_text = source if isinstance(source, str) else None
        dest_text = dest if isinstance(dest, str) else None
        
        # Task 2.5: Resolve stations to confirm corrections
        from services.station_search_service import station_search_engine
        
        src_resolved = station_search_engine.resolve(source_text) if source_text else None
        dst_resolved = station_search_engine.resolve(dest_text) if dest_text else None
        
        if src_resolved and dst_resolved:
            # Task 2.5: Build confirmation message
            confirmations = []
            if source_text and source_text.upper() != src_resolved.code and source_text.upper() != src_resolved.name.upper():
                confirmations.append(f"'{source_text}' to {src_resolved.name} ({src_resolved.code})")
            if dest_text and dest_text.upper() != dst_resolved.code and dest_text.upper() != dst_resolved.name.upper():
                confirmations.append(f"'{dest_text}' to {dst_resolved.name} ({dst_resolved.code})")
            
            correction_text = f" (Correcting {' & '.join(confirmations)})" if confirmations else ""
            
            reply = f"🔍 Initializing logistics{correction_text}. Journey from {src_resolved.name} to {dst_resolved.name}. Checking live availability..."
            
            # Update entities with canonical codes for frontend
            merged_entities["source"] = src_resolved.code
            merged_entities["destination"] = dst_resolved.code
            
            return ChatResponse(reply=reply, intent=intent, confidence=1.0, trigger_search=True, collected=merged_entities)
        else:
            reply = "🔍 I'm ready to search for trains. Where are you traveling from and to?"
            actions = [ChatAction(label="Mumbai to Delhi", type="intent", value="Mumbai to Delhi")]
    
    elif intent == 'pnr':
        pnr = merged_entities.get("pnr")
        reply = f"🎫 Retrieving telemetry for PNR: {pnr}... I'm accessing live seat availability and status data."
        actions = [ChatAction(label="Detailed Status", type="intent", value=f"PNR {pnr}")]
    
    elif intent == 'clarify':
        # Task 2.3: Neural Clarification
        reply = "🤔 Mission Parameters Uncertain. Did you mean to Search for Trains or Track a live journey?"
        actions = [
            ChatAction(label="🔍 Search Trains", type="intent", value="Search Trains"),
            ChatAction(label="📡 Track Journey", type="intent", value="Track Train")
        ]
        return ChatResponse(reply=reply, intent=intent, confidence=0.5, actions=actions)

    elif intent == 'bookings':
        reply = "🎫 Retrieving your mission history... I've found your recent bookings. Would you like to view them in the dashboard?"
        actions = [ChatAction(label="Open Bookings", type="navigate", value="/bookings")]
    elif intent == 'dashboard':
        reply = "📊 Accessing RouteMaster Central... Your dashboard is ready for review."
        actions = [ChatAction(label="View Dashboard", type="navigate", value="/dashboard")]
    elif intent == 'telegram':
        reply = "📱 Establishing Telegram uplink... You can sync your profile to our secure Telegram bot for real-time tracking."
        actions = [ChatAction(label="Sync Telegram", type="open_url", value="https://t.me/RoutemasternagarindustrisBot")]
    elif intent == 'sos':
        reply = "🚨 **EMERGENCY PROTOCOL INITIALIZED.** I am notifying emergency contacts and sharing your live telemetry. Stay calm."
        actions = [ChatAction(label="View SOS Status", type="navigate", value="/sos")]
    elif intent == 'cancel':
        reply = "💳 Initiating refund protocol... I've found your latest eligible tickets. You can manage cancellations in your bookings."
        actions = [ChatAction(label="My Bookings", type="navigate", value="/bookings")]
    elif intent == 'fare':
        reply = "💰 Accessing fare telemetry... Train costs vary by class and date. Please use the search tool for exact pricing."
        actions = [ChatAction(label="Search Trains", type="intent", value="Search Trains")]
    elif intent == 'track':
        reply = "📡 Activating live tracking... Please enter your train number or check your active bookings for live telemetry."
        actions = [ChatAction(label="Live Tracking", type="navigate", value="/dashboard")]
    elif intent == 'station':
        reply = "🏢 Station Database Online. I can provide platform info, amenities, and arrival/departure boards."
        actions = [ChatAction(label="Find Station", type="navigate", value="/dashboard")]

    return ChatResponse(reply=reply, intent=intent, confidence=1.0, actions=actions)

@router.post("", response_model=ChatResponse)
@limiter.limit("10/minute")
async def chat_message(
    request: Request,
    chat_req: ChatMessage,
    db: Session = Depends(get_db),
    user: Optional[User] = Depends(get_optional_user),
):
    if len(chat_req.message) > 2000:
        raise HTTPException(status_code=413, detail="Payload too large. Message exceeds 2000 characters.")

    start_time = time.time()
    session_id = chat_req.session_id or str(uuid.uuid4())
    session = _load_session(session_id)

    # 1. NLP Intent Detection
    from utils.nlp_router import get_local_intent
    from utils.entity_extractor import EntityExtractor
    
    intent_start = time.time()
    extracted = EntityExtractor.extract_all(chat_req.message)
    
    # Task 2.4: Sequential Context - Merge entities into session memory
    if extracted:
        current_entities = session.get("extracted_entities", {})
        session["extracted_entities"] = {**current_entities, **extracted}
    
    local_intent = await asyncio.to_thread(get_local_intent, chat_req.message)
    intent_latency = (time.time() - intent_start) * 1000
    
    intent = local_intent["intent"] if local_intent else "unknown"
    confidence = local_intent.get("confidence", 0.0) if local_intent else 0.0
    
    # Task 2.3: Confidence Triage
    if confidence > 0.0 and confidence < 0.6:
        intent = "clarify"

    llm_latency = 0.0
    if intent == "unknown" and Config.OPENROUTER_API_KEY:
        llm_start = time.time()
        try:
            # Task 6.1: Include conversational context (History)
            llm_messages = [{"role": "system", "content": "You are Diksha, the RouteMaster AI. Assist with train travel and safety. Be concise."}]
            for msg in session.get("messages", [])[-10:]:
                llm_messages.append(msg)
            llm_messages.append({"role": "user", "content": chat_req.message})
            
            ai_res = await call_openrouter_api(llm_messages)
            reply = ai_res["choices"][0]["message"]["content"]
            response_obj = ChatResponse(reply=reply, intent="llm_fallback", confidence=0.5)
            llm_latency = (time.time() - llm_start) * 1000
        except Exception as e:
            logger.error(f"LLM Call failed: {e}")
            response_obj = generate_response("fallback", chat_req.message, session)
    else:
        # Task 2.7: Intent-to-Action Mapping
        from services.chat_action_dispatcher import chat_dispatcher
        action_entities_raw = local_intent.get("entities") if local_intent else extracted
        action_entities = action_entities_raw if isinstance(action_entities_raw, dict) else {}
        action_result = await chat_dispatcher.dispatch(intent, action_entities, db, user)
        
        response_obj = generate_response(intent, chat_req.message, session, entities=action_entities)
        
        # If an action was performed, prefix the AI response with the tactical result
        if action_result:
            response_obj.reply = f"{action_result}\n\n{response_obj.reply}"

    # [Task 4.8] Self-Healing: Shed non-critical intent logs during DB stress
    db_mode = cache_service.get("DB:OPERATION_MODE")
    if db_mode != "READ_ONLY":
        intent_log = AIIntentLog(
            query=chat_req.message,
            matched_intent=response_obj.intent,
            confidence=response_obj.confidence or 0.0,
            intent_latency_ms=int(intent_latency),
            llm_latency_ms=int(llm_latency),
            timestamp=datetime.utcnow()
        )
        db.add(intent_log)
        db.commit()
    else:
        logger.warning("🛡️ [DB_SENTINEL] Load Shedding: Skipping AIIntentLog during DB Saturation.")

    session["messages"].append({"role": "user", "content": chat_req.message})
    session["messages"].append({"role": "assistant", "content": response_obj.reply})
    _save_session(session_id, session)

    return response_obj

@router.get("/history")
async def get_history(session_id: str, db: Session = Depends(get_db)):
    return {"messages": _load_session(session_id)["messages"]}

@router.delete("/history")
async def delete_history(session_id: str, db: Session = Depends(get_db)):
    """Clear chat history for a session."""
    redis_client = _get_redis()
    if redis_client:
        try:
            redis_client.delete(_session_key(session_id))
        except Exception as e:
            logger.warning(f"Failed to delete session from Redis: {e}")
            
    if session_id in _local_sessions:
        del _local_sessions[session_id]
        
    return {"status": "success", "message": "History cleared"}


def count_tokens(text: str) -> int:
    if not text: return 0
    return len(text) // 4

