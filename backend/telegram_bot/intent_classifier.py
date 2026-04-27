"""
Intent Classifier
=================
NLP-based intent recognition for natural language understanding.
"""

import re
import logging
from typing import Optional, Dict, Any, Tuple
from dataclasses import dataclass
from datetime import datetime
import asyncio
from collections import deque

from .schemas import IntentType, UserContext
from .config import bot_config

logger = logging.getLogger(__name__)


@dataclass
class IntentResult:
    """Result of intent classification."""
    intent: IntentType
    confidence: float
    entities: Dict[str, Any]
    raw_text: str
    suggested_response: Optional[str] = None


class IntentClassifier:
    """
    NLP-based intent classifier with pattern matching and entity extraction.
    Uses keyword patterns, regex, and context for classification.
    """
    
    # Intent patterns with keywords and regex
    INTENT_PATTERNS = {
        IntentType.SEARCH_TRAINS: {
            "keywords": ["search", "find", "trains", "routes", "journey", "travel", "go to", "trip"],
            "patterns": [
                r"(?:show|find|search|list)\s+(?:me\s+)?(?:the\s+)?(?:trains?\s+)?(?:from\s+\w+\s+)?(?:to\s+\w+)",
                r"(?:trains?\s+)?(?:from|to)\s+\w+\s+(?:to|from)\s+\w+",
                r"(?:train|rail)\s+(?:schedule|timetable|routes?)",
            ],
            "priority": 1
        },
        IntentType.BOOK_TICKET: {
            "keywords": ["book", "booking", "reserve", "ticket", "purchase", "buy"],
            "patterns": [
                r"(?:book|reserve|buy)\s+(?:a\s+)?(?:train\s+)?ticket",
                r"(?:i\s+)?(?:want|need|would like)\s+(?:to\s+)?(?:book|reserve|buy)",
                r"(?:train\s+)?ticket\s+(?:from|to)",
            ],
            "priority": 2
        },
        IntentType.CHECK_PNR: {
            "keywords": ["pnr", "status", "check", "verify"],
            "patterns": [
                r"(?:check|status|verify)\s+(?:my\s+)?pnr",
                r"pnr\s*(?::|number|#)?\s*\d{10}",
                r"(?:what(?:'s| is)?\s+)?(?:my\s+)?pnr\s+(?:status|number)",
            ],
            "priority": 3
        },
        IntentType.VIEW_BOOKINGS: {
            "keywords": ["bookings", "my bookings", "history", "past", "previous", "tickets"],
            "patterns": [
                r"(?:my\s+)?(?:bookings?|tickets?|reservations?)",
                r"(?:show|list|view)\s+(?:my\s+)?(?:bookings?|tickets?)",
                r"(?:past|previous|old)\s+(?:journeys?|travels?|bookings?)",
            ],
            "priority": 4
        },
        IntentType.CANCEL_BOOKING: {
            "keywords": ["cancel", "cancellation", "refund", "abort"],
            "patterns": [
                r"(?:cancel|abort)\s+(?:my\s+)?(?:booking|ticket)",
                r"(?:request\s+)?(?:cancellation|refund)",
                r"(?:i\s+)?(?:want|need)\s+(?:to\s+)?cancel",
            ],
            "priority": 5
        },
        IntentType.DOWNLOAD_TICKET: {
            "keywords": ["download", "pdf", "ticket", "eticket", "copy"],
            "patterns": [
                r"(?:download|get|show)\s+(?:my\s+)?(?:ticket|pdf|eticket)",
                r"(?:ticket|pdf)\s+(?:download|copy|file)",
            ],
            "priority": 6
        },
        IntentType.TRAIN_STATUS: {
            "keywords": ["status", "running", "delayed", "on time", "arrived"],
            "patterns": [
                r"(?:train\s+)?(?:status|running\s+(?:status|on|time))",
                r"(?:is|are)\s+(?:the\s+)?(?:train\s+)?(?:delayed|on\s+time|arrived)",
                r"(?:train\s+)?(?:delay|arrival|departure)\s+(?:status|info)",
            ],
            "priority": 7
        },
        IntentType.STATION_DEPARTURES: {
            "keywords": ["departures", "arrivals", "platform", "schedule"],
            "patterns": [
                r"(?:station\s+)?(?:departures?|arrivals?|platform)",
                r"(?:what(?:'s| is)?\s+)?(?:at|on)\s+(?:the\s+)?station",
                r"(?:train\s+)?(?:schedule|timetable)\s+(?:at|for)",
            ],
            "priority": 8
        },
        IntentType.MY_PROFILE: {
            "keywords": ["profile", "account", "settings", "my"],
            "patterns": [
                r"(?:my\s+)?(?:profile|account|settings)",
                r"(?:show|view|edit)\s+(?:my\s+)?(?:profile|account)",
            ],
            "priority": 9
        },
        IntentType.MY_WALLET: {
            "keywords": ["wallet", "balance", "money", "payment", "cash"],
            "patterns": [
                r"(?:my\s+)?(?:wallet|balance|payment)",
                r"(?:add|load|top\s+up)\s+(?:money|cash|wallet)",
            ],
            "priority": 10
        },
        IntentType.SOS_EMERGENCY: {
            "keywords": ["sos", "emergency", "help", "danger", "accident"],
            "patterns": [
                r"(?:sos|emergency|help|danger|accident)",
                r"(?:i(?:'m| am)?\s+)?(?:in\s+)?(?:trouble|danger|emergency)",
            ],
            "priority": 100  # Highest priority for emergencies
        },
        IntentType.SAFETY_STATUS: {
            "keywords": ["safety", "safe", "security", "status"],
            "patterns": [
                r"(?:safety|security)\s+(?:status|check)",
                r"(?:am i|is)\s+(?:safe|secure)",
                r"(?:train\s+)?(?:safety|security)\s+(?:status|info)",
            ],
            "priority": 11
        },
        IntentType.HELP: {
            "keywords": ["help", "guide", "how", "what can you do", "commands"],
            "patterns": [
                r"(?:help|guide|how\s+(?:to|does)|what\s+(?:can|to)|commands?)",
                r"(?:what(?:'s| can)?\s+)?(?:can|do)\s+(?:you\s+)?(?:do|help)",
            ],
            "priority": 12
        },
        IntentType.START: {
            "keywords": ["start", "begin", "hi", "hello", "hey"],
            "patterns": [
                r"^(?:start|begin|hi|hello|hey|namaste)",
                r"^start|^help",
            ],
            "priority": 1
        },
        IntentType.MAIN_MENU: {
            "keywords": ["menu", "home", "main", "back"],
            "patterns": [
                r"(?:main\s+)?menu|home|back",
                r"/menu|/home",
            ],
            "priority": 1
        },
    }
    
    # Entity extraction patterns
    ENTITY_PATTERNS = {
        "pnr": r"\b(\d{10})\b",
        "train_no": r"(?:train\s*)?(?:no\.?|number\s*)?(\d{5,7})\b",
        "date": r"(?:on|date)?\s*(\d{4}[-/]\d{2}[-/]\d{2}|\d{2}[-/]\d{2}[-/]\d{4}|\d{2}\s+(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\s+\d{4})",
        "station_code": r"\b([A-Z]{3,5})\b(?:\s+(?:station|to|from))?",
        "phone": r"(?:phone|mobile|call)?\s*:?\s*(\+?\d{10,12})",
        "email": r"([a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,})",
    }
    
    def __init__(self):
        self._metrics: deque = deque(maxlen=1000)
        self._metrics_lock = asyncio.Lock()
        self._context_cache: Dict[int, UserContext] = {}
        
        if not bot_config.enable_nlp:
            logger.info("NLP disabled, using basic pattern matching")
    
    async def classify(
        self, 
        text: str, 
        context: Optional[UserContext] = None,
        user_id: Optional[int] = None
    ) -> IntentResult:
        """
        Classify user intent from text.
        
        Args:
            text: User input text
            context: Previous conversation context
            user_id: User ID for context caching
            
        Returns:
            IntentResult with intent, confidence, and entities
        """
        start_time = datetime.utcnow()
        
        # Clean and normalize text
        clean_text = self._preprocess(text)
        
        # Extract entities
        entities = self._extract_entities(clean_text)
        
        # Classify intent
        intent, confidence, matched_pattern = self._classify_intent(clean_text, entities)
        
        # Use context to refine intent
        if context and intent == IntentType.UNKNOWN:
            intent = self._refine_from_context(clean_text, context)
        
        # Calculate duration
        duration_ms = (datetime.utcnow() - start_time).total_seconds() * 1000
        
        # Record metrics
        async with self._metrics_lock:
            self._metrics.append({
                "timestamp": start_time,
                "intent": intent.value,
                "confidence": confidence,
                "duration_ms": duration_ms,
                "success": confidence > 0.5
            })
        
        # Generate suggested response
        suggested_response = self._generate_suggested_response(intent, entities)
        
        return IntentResult(
            intent=intent,
            confidence=confidence,
            entities=entities,
            raw_text=text,
            suggested_response=suggested_response
        )
    
    def _preprocess(self, text: str) -> str:
        """Preprocess text for classification."""
        if not text:
            return ""
        
        # Convert to lowercase
        text = text.lower().strip()
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        # Remove Telegram command prefix
        text = re.sub(r'^/', '', text)
        
        return text
    
    def _extract_entities(self, text: str) -> Dict[str, Any]:
        """Extract named entities from text."""
        entities = {}
        
        for entity_name, pattern in self.ENTITY_PATTERNS.items():
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                # Handle multiple matches
                if len(matches) == 1:
                    entities[entity_name] = matches[0]
                else:
                    entities[entity_name] = matches
        
        # Extract station names (simple heuristic)
        station_entities = self._extract_stations(text)
        if station_entities:
            entities["stations"] = station_entities
        
        return entities
    
    def _extract_stations(self, text: str) -> Dict[str, str]:
        """Extract station names and codes."""
        stations = {}
        
        # Common station patterns
        patterns = [
            (r"from\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", "from"),
            (r"to\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)*)", "to"),
            (r"between\s+([A-Z][a-z]+)\s+(?:and|&)\s+([A-Z][a-z]+)", "between"),
        ]
        
        for pattern, direction in patterns:
            matches = re.findall(pattern, text, re.IGNORECASE)
            if matches:
                if direction == "between" and len(matches[0]) == 2:
                    stations["from"] = matches[0][0]
                    stations["to"] = matches[0][1]
                elif direction in ["from", "to"]:
                    stations[direction] = matches[0]
        
        return stations
    
    def _classify_intent(
        self, 
        text: str, 
        entities: Dict[str, Any]
    ) -> Tuple[IntentType, float, Optional[str]]:
        """Classify intent based on patterns and keywords."""
        best_intent = IntentType.UNKNOWN
        best_confidence = 0.0
        best_pattern = None
        
        for intent, config in self.INTENT_PATTERNS.items():
            # Check priority (SOS always wins)
            if intent == IntentType.SOS_EMERGENCY:
                if any(kw in text for kw in config["keywords"]):
                    return IntentType.SOS_EMERGENCY, 1.0, "keyword"
            
            # Check patterns
            for pattern in config["patterns"]:
                match = re.search(pattern, text, re.IGNORECASE)
                if match:
                    confidence = 0.8 + (0.1 * (1 / config["priority"]))
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_intent = intent
                        best_pattern = pattern
                    break
            
            # Check keywords if no pattern matched
            if best_confidence < 0.5:
                keyword_count = sum(1 for kw in config["keywords"] if kw in text)
                if keyword_count > 0:
                    confidence = 0.3 + (0.1 * keyword_count)
                    if confidence > best_confidence:
                        best_confidence = confidence
                        best_intent = intent
                        best_pattern = "keyword"
        
        # Boost confidence if entities support intent
        if entities:
            if best_intent in [IntentType.CHECK_PNR, IntentType.TRACK_PNR] and "pnr" in entities:
                best_confidence = min(1.0, best_confidence + 0.2)
            elif best_intent == IntentType.SEARCH_TRAINS and "stations" in entities:
                best_confidence = min(1.0, best_confidence + 0.2)
            elif best_intent == IntentType.TRAIN_STATUS and "train_no" in entities:
                best_confidence = min(1.0, best_confidence + 0.2)
        
        return best_intent, best_confidence, best_pattern
    
    def _refine_from_context(self, text: str, context: UserContext) -> IntentType:
        """Refine intent using conversation context."""
        # If user is in booking flow and sends a station name
        if context.state.value in ["searching", "booking"]:
            if "stations" in self._extract_entities(text):
                return context.intent if context.intent else IntentType.SEARCH_TRAINS
        
        # If user says "back", return to previous intent
        if text in ["back", "previous", "cancel"]:
            return IntentType.BACK
        
        # If user says "menu" or "home"
        if text in ["menu", "home", "main"]:
            return IntentType.MAIN_MENU
        
        return IntentType.UNKNOWN
    
    def _generate_suggested_response(
        self, 
        intent: IntentType, 
        entities: Dict[str, Any]
    ) -> Optional[str]:
        """Generate a suggested response based on intent and entities."""
        responses = {
            IntentType.SEARCH_TRAINS: "Let me search for trains for you...",
            IntentType.BOOK_TICKET: "I'll help you book a ticket. Please provide the details.",
            IntentType.CHECK_PNR: "Checking PNR status...",
            IntentType.VIEW_BOOKINGS: "Fetching your bookings...",
            IntentType.CANCEL_BOOKING: "Processing cancellation request...",
            IntentType.DOWNLOAD_TICKET: "Preparing your ticket...",
            IntentType.TRAIN_STATUS: "Checking train status...",
            IntentType.STATION_DEPARTURES: "Getting station information...",
            IntentType.MY_PROFILE: "Opening your profile...",
            IntentType.MY_WALLET: "Checking your wallet balance...",
            IntentType.SOS_EMERGENCY: "🚨 Emergency services activated!",
            IntentType.SAFETY_STATUS: "Checking safety status...",
            IntentType.HELP: "Here are the available commands...",
            IntentType.START: "Welcome! How can I help you?",
            IntentType.MAIN_MENU: "Returning to main menu...",
            IntentType.UNKNOWN: "I didn't understand that. Can you please rephrase?",
        }
        
        return responses.get(intent)
    
    def get_metrics(self) -> dict:
        """Get classifier metrics."""
        if not self._metrics:
            return {"total_classifications": 0, "accuracy": 0.0}
        
        total = len(self._metrics)
        successful = sum(1 for m in self._metrics if m["success"])
        by_intent = {}
        
        for m in self._metrics:
            intent = m["intent"]
            if intent not in by_intent:
                by_intent[intent] = {"total": 0, "success": 0}
            by_intent[intent]["total"] += 1
            if m["success"]:
                by_intent[intent]["success"] += 1
        
        return {
            "total_classifications": total,
            "successful_classifications": successful,
            "accuracy": successful / total if total > 0 else 0.0,
            "by_intent": by_intent,
            "avg_duration_ms": sum(m["duration_ms"] for m in self._metrics) / total if total > 0 else 0
        }


# Global instance
intent_classifier = IntentClassifier()