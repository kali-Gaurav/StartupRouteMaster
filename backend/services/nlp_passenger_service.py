import logging
import re
import json
from typing import List, Dict, Any
import google.generativeai as genai
from config import Config

logger = logging.getLogger(__name__)

class NLPPassengerService:
    """
    Task 29: NLP Passenger Schema Mapper.
    Uses Gemini to extract structured passenger data from natural language.
    """
    def __init__(self):
        # Configure Gemini
        self.api_key = Config.GEMINI_API_KEY if hasattr(Config, 'GEMINI_API_KEY') else None
        if self.api_key:
            genai.configure(api_key=self.api_key)
            self.model = genai.GenerativeModel('gemini-2.5-flash')
        else:
            logger.warning("GEMINI_API_KEY not configured. NLP Passenger parsing will fail or mock.")

    def normalize_berth(self, raw_berth: str) -> str:
        """Task 29.3: Berth preference normalization."""
        if not raw_berth: return None
        raw = raw_berth.lower().strip()
        if raw in ['lb', 'lower', 'lower berth', 'down', 'bottom']: return 'LOWER'
        if raw in ['mb', 'middle', 'middle berth', 'mid']: return 'MIDDLE'
        if raw in ['ub', 'upper', 'upper berth', 'top', 'up']: return 'UPPER'
        if raw in ['sl', 'side lower', 'side lower berth']: return 'SIDE_LOWER'
        if raw in ['su', 'side upper', 'side upper berth']: return 'SIDE_UPPER'
        return None

    def detect_identity_document(self, text: str) -> Dict[str, str]:
        """Task 29.9: Identity document type mapping."""
        # Aadhar: 12 digits, often formatted as xxxx xxxx xxxx
        text_clean = text.replace(" ", "")
        aadhar_match = re.search(r"(\d{12})", text_clean) # Removed \b because text_clean merges words with digits
        if aadhar_match:
            return {"type": "AADHAR", "number": aadhar_match.group(1)}
            
        # Voter ID (EPIC): 3 letters followed by 7 digits
        voter_match = re.search(r"\b[A-Z]{3}\d{7}\b", text.upper())
        if voter_match:
            return {"type": "VOTER_ID", "number": voter_match.group()}
            
        return None

    def post_process_passengers(self, passengers: List[Dict[str, Any]], raw_text: str) -> List[Dict[str, Any]]:
        """Applies IRCTC specific business rules to the extracted data."""
        processed = []
        for p in passengers:
            name = str(p.get("name", "")).strip()
            age = int(p.get("age", 0))
            
            # Task 29.6: Validation against IRCTC character limits (16 chars)
            if len(name) > 16:
                name = name[:16].strip()
                p["warnings"] = p.get("warnings", []) + ["Name truncated to 16 characters for IRCTC."]

            # Task 29.4: Senior Citizen quota detection
            is_senior = age >= 60 if p.get("gender", "").upper() == "M" else age >= 58 # Basic rule
            
            # Task 29.5: Child passenger handling (Age < 5)
            is_child = age < 5
            
            # Confidence Scoring (Task 29.10)
            confidence = 100
            if not name: confidence -= 40
            if not age: confidence -= 30
            if not p.get("gender"): confidence -= 30
            
            # Document mapping (check raw text for docs near the name)
            doc = self.detect_identity_document(raw_text)

            processed.append({
                "name": name,
                "age": age,
                "gender": p.get("gender", "M").upper(), # Default to M if unknown, frontend will flag
                "berth_preference": self.normalize_berth(p.get("berth_preference")),
                "is_senior_citizen": is_senior,
                "is_child": is_child,
                "document": doc,
                "confidence_score": max(0, confidence),
                "warnings": p.get("warnings", [])
            })
            
        return processed

    def parse_passengers(self, text: str) -> Dict[str, Any]:
        """
        Tasks 29.1, 29.2, 29.7, 29.8: Core Gemini extraction logic.
        """
        if not self.api_key:
            # Fallback for dev/test without API key
            return {"success": False, "message": "Gemini API key missing"}

        prompt = f"""
        Extract passenger details from the following text. 
        Auto-correct common typos in Indian names (Task 29.7).
        Infer gender from the name if not explicitly stated (Task 29.2).
        Support multiple passengers if present (Task 29.8).
        
        Text: "{text}"
        
        Return ONLY a raw JSON array of objects with these keys: 
        "name" (string), "age" (number), "gender" (string M/F/T), "berth_preference" (string, if any).
        Do NOT wrap in ```json or markdown blocks.
        """
        
        try:
            response = self.model.generate_content(prompt)
            raw_json = response.text.strip()
            
            # Clean markdown if Gemini ignored instructions
            if raw_json.startswith("```json"):
                raw_json = raw_json[7:-3].strip()
            elif raw_json.startswith("```"):
                raw_json = raw_json[3:-3].strip()
                
            extracted = json.loads(raw_json)
            
            if not isinstance(extracted, list):
                extracted = [extracted]
                
            processed = self.post_process_passengers(extracted, text)
            
            return {
                "success": True,
                "passengers": processed,
                "raw_text_length": len(text)
            }
            
        except Exception as e:
            logger.error(f"Failed to parse passengers via NLP: {e}")
            return {"success": False, "message": str(e)}

nlp_passenger_service = NLPPassengerService()
