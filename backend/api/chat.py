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
                session_data = json.loads(raw)
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

def generate_response(intent: str, message: str, session_data: Dict[str, Any]) -> ChatResponse:
    reply = f"Detected intent: {intent}. How can I help?"
    if intent == 'search': reply = "🔍 Where would you like to go?"
    return ChatResponse(reply=reply, intent=intent, confidence=0.9)

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
    if extracted: session.setdefault("extracted_entities", {}).update(extracted)
    
    local_intent = await asyncio.to_thread(get_local_intent, chat_req.message)
    intent_latency = (time.time() - intent_start) * 1000
    
    intent = local_intent["intent"] if local_intent else "unknown"
    confidence = local_intent.get("confidence", 0.0) if local_intent else 0.0
    
    llm_latency = 0.0
    if intent == "unknown" and Config.OPENROUTER_API_KEY:
        llm_start = time.time()
        try:
            # Task 6.1: Include conversational context (History)
            llm_messages = [{"role": "system", "content": "You are Diksha, the RouteMaster AI. Assist with train travel and safety."}]
            for msg in session.get("messages", [])[-20:]:
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
        response_obj = generate_response(intent, chat_req.message, session)

    # Subtask 8.4 & 8.7: Record Intent & Latency
    intent_log = AIIntentLog(
        query=chat_req.message,
        matched_intent=response_obj.intent,
        confidence=response_obj.confidence,
        intent_latency_ms=int(intent_latency),
        llm_latency_ms=int(llm_latency),
        timestamp=datetime.utcnow()
    )
    db.add(intent_log)
    db.commit()

    session["messages"].append({"role": "user", "content": chat_req.message})
    session["messages"].append({"role": "assistant", "content": response_obj.reply})
    _save_session(session_id, session)

    return response_obj

@router.get("/history")
async def get_history(session_id: str, db: Session = Depends(get_db)):
    return {"messages": _load_session(session_id)["messages"]}


def count_tokens(text: str) -> int:
    if not text: return 0
    return len(text) // 4

