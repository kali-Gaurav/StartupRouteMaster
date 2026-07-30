from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends
from typing import Optional, Dict, Any
import json
import asyncio
import uuid
import logging
from datetime import datetime
import httpx

from database.config import Config
from api.communication.chat import (
    _load_session, _save_session, count_tokens, 
    generate_response, TOKEN_BUDGET
)
from utils.nlp_router import get_local_intent

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat/ws", tags=["chat_ws"])

async def stream_openrouter_api(messages: list, websocket: WebSocket):
    """Streams response from OpenRouter and forwards to WebSocket."""
    if not Config.OPENROUTER_API_KEY:
        await websocket.send_json({"type": "error", "message": "OpenRouter API key not configured."})
        return ""

    full_content = ""
    try:
        async with httpx.AsyncClient() as client:
            async with client.stream(
                "POST",
                "https://openrouter.ai/api/v1/chat/completions",
                headers={
                    "Authorization": f"Bearer {Config.OPENROUTER_API_KEY}",
                    "HTTP-Referer": "https://github.com/Gaurav-Nagar-official/startupV2",
                    "X-Title": "RouteMaster-Chat-Stream",
                },
                json={
                    "model": "openai/gpt-4o", # Specific model for streaming
                    "messages": messages,
                    "stream": True,
                },
                timeout=60.0,
            ) as response:
                response.raise_for_status()
                
                async for line in response.aiter_lines():
                    if not line or not line.startswith("data: "):
                        continue
                    
                    data_str = line[6:].strip()
                    if data_str == "[DONE]":
                        break
                    
                    try:
                        data = json.loads(data_str)
                        chunk = data["choices"][0]["delta"].get("content", "")
                        if chunk:
                            full_content += chunk
                            await websocket.send_json({"type": "token", "token": chunk})
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
                        
    except Exception as e:
        logger.error(f"Streaming error: {e}")
        await websocket.send_json({"type": "error", "message": str(e)})
    
    return full_content

@router.websocket("")
async def chat_websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time streaming chat.
    PROTOCOL:
    1. Client connects.
    2. Server accepts (no initial 403).
    3. Client sends first message with optional session_id.
    """
    await websocket.accept()
    logger.info("Chat WebSocket connected and accepted.")
    
    try:
        while True:
            raw_data = await websocket.receive_text()
            data = json.loads(raw_data)
            
            message = data.get("message")
            session_id = data.get("session_id") or str(uuid.uuid4())
            
            if not message:
                continue
                
            session = _load_session(session_id)
            session.setdefault("messages", []).append({
                "role": "user",
                "content": message,
                "timestamp": datetime.utcnow().isoformat()
            })

            # 1. Local Pre-processing
            from utils.entity_extractor import EntityExtractor
            extracted = EntityExtractor.extract_all(message)
            if extracted:
                session.setdefault("extracted_entities", {}).update(extracted)

            local_intent_data = get_local_intent(message)
            intent = "unknown"
            if local_intent_data:
                intent = local_intent_data["intent"]

            # Fallback to search intent if stations were found
            if intent == 'unknown' and "source" in session["extracted_entities"] and "destination" in session["extracted_entities"]:
                intent = 'search'

            # 2. Decision: Local Response or AI Stream
            if intent != "unknown":
                # Local Response
                response_obj = generate_response(intent, message, session)
                await websocket.send_json({
                    "type": "final",
                    "reply": response_obj.reply,
                    "actions": [a.dict() for a in (response_obj.actions or [])],
                    "intent": intent,
                    "session_id": session_id
                })
                ai_reply_content = response_obj.reply
            else:
                # AI Streaming Response
                ai_messages = [
                    {"role": "system", "content": "You are Diksha, RouteMaster's AI Brain. Be concise and helpful."}
                ]
                
                # Context retention
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

                # Stream tokens
                ai_reply_content = await stream_openrouter_api(ai_messages, websocket)
                
                # Send final packet
                await websocket.send_json({
                    "type": "final",
                    "reply": ai_reply_content,
                    "intent": "llm_stream",
                    "session_id": session_id
                })

            # 3. Save Session
            session["messages"].append({
                "role": "assistant",
                "content": ai_reply_content,
                "timestamp": datetime.utcnow().isoformat()
            })
            _save_session(session_id, session)

    except WebSocketDisconnect:
        logger.info("Chat WebSocket disconnected")
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        try:
            await websocket.send_json({"type": "error", "message": "An internal error occurred."})
        except:
            pass
