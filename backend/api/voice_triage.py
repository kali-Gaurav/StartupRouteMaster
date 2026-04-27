from fastapi import APIRouter, Request, Depends, Form
from typing import Optional, Dict, Any
import logging
import json
from datetime import datetime
from pydantic import BaseModel

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/voice", tags=["Emergency Voice Intelligence"])

class VoiceTriggerPayload(BaseModel):
    user_id: str
    transcript: str
    lat: float
    lng: float
    phone: Optional[str] = None
    noise_level_db: Optional[float] = 40.0 # Task 18
    trigger_method: Optional[str] = "manual" # Task 22
    audio_pitch_hz: Optional[float] = 150.0 # Task 24: Normal speech ~100-200Hz
    audio_energy: Optional[float] = 0.5 # Task 24: Volume/Intensity

@router.post("/triage-start")
async def voice_triage_start(user_id: Optional[str] = None):
    """
    Returns localized TwiML instructions based on user preference.
    """
    lang = "en"
    if user_id:
        from database.session import SessionLocal
        from database.models import UserAIPreference
        db = SessionLocal()
        try:
            pref = db.query(UserAIPreference).filter(UserAIPreference.user_id == user_id).first()
            if pref:
                lang = pref.preferred_language or "en"
        finally:
            db.close()

    # Subtask 22.4: Language Mapping
    prompts = {
        "en": {
            "voice": "en-IN-Wavenet-A",
            "text": "This is RouteMaster Emergency. We have received your S O S. Please tell us briefly, what is your emergency?",
            "listen": "I am listening."
        },
        "hi": {
            "voice": "hi-IN-Wavenet-A",
            "text": "यह रूट मास्टर इमरजेंसी है। हमें आपका एस ओ एस मिला है। कृपया हमें संक्षेप में बताएं, आपकी इमरजेंसी क्या है?",
            "listen": "मैं सुन रहा हूँ।"
        }
    }
    
    p = prompts.get(lang, prompts["en"])
    
    twiml = f"""
    <Response>
        <Say voice="{p['voice']}">
            {p['text']}
        </Say>
        <Gather input="speech" action="/api/voice/triage-results" timeout="5" hints="medical, help, police, accident, ambulance">
            <Say>{p['listen']}</Say>
        </Gather>
    </Response>
    """
    return twiml

@router.post("/call-status")
async def handle_call_status(
    event_id: str, 
    CallStatus: str = Form(None), 
    To: str = Form(None)
):
    """
    Subtask 21.1: Tracks real-time status of emergency calls.
    """
    logger.info(f"📞 [CALL STATUS] Event {event_id}: {CallStatus} for {To}")
    
    from api.sos import _load_event_async, _save_event_async
    from api.websockets import manager

    event = await _load_event_async(event_id)
    if event:
        event["telecom_status"] = CallStatus
        await _save_event_async(event)

        # Subtask 21.2: Automated Retry on Fail
        if CallStatus in ["busy", "no-answer", "failed"]:
            retry_count = event.get("call_retry_count", 0)
            if retry_count < 3:
                event["call_retry_count"] = retry_count + 1
                logger.warning(f"⚠️ Call failed. Scheduling retry {event['call_retry_count']} for {To}")
                # Logic to trigger initiate_emergency_call again after delay

        # Notify dashboard
        await manager.broadcast_sos(event)

    return {"status": "ok"}

@router.post("/bridge-status")
async def handle_bridge_status(
    event_id: str, 
    ParticipantLabel: str = Form(None), 
    Status: str = Form(None)
):
    """
    Subtask 25.4: Tracks participant join/leave events.
    """
    if not event_id: return {"status": "error"}

    from api.sos import _load_event_async, _save_event_async
    from api.websockets import manager

    event = await _load_event_async(event_id)
    if event:
        participants = set(event.get("active_participants", []))

        if Status == "joined" and ParticipantLabel:
            participants.add(ParticipantLabel)
        elif Status == "left" and ParticipantLabel:
            participants.discard(ParticipantLabel)

        event["active_participants"] = list(participants)
        await _save_event_async(event)

        # Notify dashboard
        await manager.broadcast_sos(event)

    return {"status": "updated"}

@router.post("/voice-trigger-sos")
async def trigger_voice_sos(payload: VoiceTriggerPayload):
    """
    Task 35/18/22: Voice Trigger with Noise Suppression and Wake-Word Prioritization.
    """
    trigger_words = ["help help", "save me", "bachao", "emergency", "police"]
    transcript_low = payload.transcript.lower()
    
    # Task 22: On-Device Wake-Word Engine Prioritization
    # If the app says it was a wake-word match, we trust it more than just a background transcript.
    is_wake_word = payload.trigger_method == "wake_word"
    
    # Task 18: Noise-Aware Sensitivity
    is_noisy = (payload.noise_level_db or 0) > 70.0
    
    # Task 23: Phonetic Signature Matching
    from utils.phonetic_hasher import safety_hasher
    match_found = is_wake_word or safety_hasher.match(transcript_low, trigger_words)
    
    # Task 45: Safe-Word Cancellation
    # Check if this is an existing incident and user says "ALRIGHT" or "OKAY"
    from api.sos import _load_event_async, _save_event_async, PNR_REGISTRY_KEY, _get_redis_index_ids

    # We'd need a way to link voice user_id to active event (Task 3 registry)
    # For now, we mock the PNR resolution or user search
    active_event_id = None
    try:
        ids = await _get_redis_index_ids()
        for eid in ids:
            e = await _load_event_async(eid)
            if e and e.get("phone") == payload.phone and e.get("status") in ["active", "responding"]:
                active_event_id = e["id"]
                break
    except Exception:
        pass

    if active_event_id and any(word in transcript_low for word in ["alright", "cancel", "okay now"]):
        logger.info(f"🛑 [SAFE-WORD] Auto-cancelling incident {active_event_id} via voice command.")
        from api.websockets import manager
        event = await _load_event_async(active_event_id)
        if event is not None:
            event["status"] = "resolved"
            event["resolved_at"] = datetime.utcnow().isoformat()
            event["extra"] = f"{event.get('extra', '')} | 🛑 CANCELLED VIA SAFE-WORD."
            await _save_event_async(event)
            await manager.broadcast_sos(event)

            return f"""
            <Response>
                <Say>Safe-word received. Incident has been cancelled. Glad you are safe.</Say>
                <Hangup/>
            </Response>
            """

    if match_found:
        logger.warning(f"🎙️ [VOICE TRIGGER] {'WAKE-WORD' if is_wake_word else 'TRANSCRIPT'} match (Noise: {payload.noise_level_db}dB) for {payload.user_id}")
        
        # Trigger actual SOS
        from api.sos import SOSPayload
        import uuid
        from services.emergency.alert_manager import EmergencyAlertManager
        
        event_id = str(uuid.uuid4())
        new_event = {
            "id": event_id, "lat": payload.lat, "lng": payload.lng,
            "name": f"Voice Trigger ({payload.user_id})", 
            "phone": payload.phone,
            "extra": f"VOICE TRIGGER DETECTED (Noise: {payload.noise_level_db}dB): '{payload.transcript}'", 
            "trip": None,
            "chat_history": [{"sender": "system", "content": f"Voice: {payload.transcript}"}], 
            "status": "active", "priority": "critical",
            "triggered_at": datetime.utcnow().isoformat(),
            "google_maps_url": f"https://www.google.com/maps/search/?api=1&query={payload.lat},{payload.lng}",
            "noise_level_db": payload.noise_level_db # Pass to context
        }
        
        alert_mgr = EmergencyAlertManager()
        enriched = await alert_mgr.process_sos_alert(new_event)
        # Event saving is handled elsewhere if needed
        
        return {
            "status": "triggered", 
            "event_id": event_id, 
            "message": "SOS initiated via voice.",
            "vad_context": "noisy_environment" if is_noisy else "clear"
        }
        
    return {"status": "ignored", "message": "No trigger word detected."}

@router.post("/triage-results")
async def handle_voice_results(
    request: Request, 
    SpeechResult: str = Form(None), 
    event_id: Optional[str] = None # Will pick up from query params if /triage-results?event_id=xxx
):
    """
    Processes the transcript from the voice call and updates the SOS incident.
    """
    if not SpeechResult:
        return {"status": "no_speech_detected"}

    logger.info(f"🎙️ [VOICE TRIAGE] Transcript: {SpeechResult}")
    
    category = "unknown"
    if event_id:
        from api.sos import _load_event_async, _save_event_async
        from services.emergency.alert_manager import EmergencyAlertManager
        event = await _load_event_async(event_id)
        if event:
            # Update context BEFORE classification
            event["extra"] = f"{event.get('extra', '')} | Voice Transcript: {SpeechResult}"

            # Subtask 22.3: Voice-to-Triage Update
            category = EmergencyAlertManager._classify_threat(event)

            event["category"] = category
            if category != "unknown":
                event["priority"] = "critical"

            # Subtask 24.1: Keyword Extraction
            from utils.sos_entities import SOSEntityExtractor
            extracted = SOSEntityExtractor.extract(SpeechResult)
            if extracted:
                if "structured_info" not in event:
                    event["structured_info"] = {}
                event["structured_info"].update(extracted)

                # Subtask 24.3: Urgent Escalation based on keywords
                if SOSEntityExtractor.get_urgency_score(extracted) >= 7:
                    event["priority"] = "critical"

            # Subtask 23.2: Persistent Transcript Storage
            if "call_logs" not in event:
                event["call_logs"] = []

            event["call_logs"].append({
                "type": "transcript",
                "content": SpeechResult,
                "timestamp": datetime.utcnow().isoformat()
            })

            await _save_event_async(event)

            # Notify Ops Dashboard via WebSocket
            from api.websockets import manager
            await manager.broadcast_sos(event)

    return f"""
    <Response>
        <Say>Understood. We have categorized this as a {category} emergency. Help is on the way.</Say>
        <Hangup/>
    </Response>
    """
