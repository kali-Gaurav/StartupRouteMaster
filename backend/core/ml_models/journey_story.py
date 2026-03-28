import logging
from typing import Dict, Any, List, Optional
from core.ml_integration import HybridMLModel
from core.data_structures import Persona

logger = logging.getLogger("ml.journey_story")

class JourneyStoryModel(HybridMLModel):
    """
    [Task 30] ML-Inspired Journey Story Classifier.
    Uses a multi-dimensional scoring matrix to select the best natural language 
    description for a route based on segments, delays, and persona.
    """
    
    def __init__(self):
        super().__init__("journey_story_v1", "classification")
        self.loaded = True # Template-based "Model" is always loaded

    def load_from_file(self, model_path: Optional[str] = None) -> bool:
        """
        Implementation of abstract method from MLModel.
        As a template-based model, it doesn't need external files.
        """
        self.loaded = True
        return True

    async def predict(self, features: Dict[str, Any]) -> str:
        """Async wrapper for compatibility."""
        return self.predict_sync(features)

    def predict_sync(self, features: Dict[str, Any]) -> str:
        """
        Classifies a route into one of 10+ story categories (Synchronous).
        """
        persona = features.get("persona", Persona.STANDARD)
        segments = features.get("segments", 1)
        delay_penalty = features.get("delay_penalty", 0)
        cost = features.get("cost", 0)
        duration = features.get("duration", 0)
        survival = features.get("survival", 1.0)
        
        # Scoring Matrix
        scores = {
            "DIRECT_SPEED": 0,
            "ECONOMY_CHOICE": 0,
            "RELIABLE_TRAVEL": 0,
            "LEISURELY_PATH": 0,
            "RISKY_BUT_FAST": 0
        }
        
        # 1. Feature Analysis
        if segments == 1: scores["DIRECT_SPEED"] += 50
        if persona == Persona.BUDGET: scores["ECONOMY_CHOICE"] += 40
        if survival > 0.95: scores["RELIABLE_TRAVEL"] += 30
        if duration > 1440: scores["LEISURELY_PATH"] += 20
        if delay_penalty > 1000: scores["RISKY_BUT_FAST"] += 40
        
        # 2. Select Max Score Category
        best_cat = max(scores, key=scores.get)
        
        # 3. Natural Language Mapping
        templates = {
            "DIRECT_SPEED": "A high-speed direct connection. Best for time-sensitive travel.",
            "ECONOMY_CHOICE": "The most budget-friendly route found, prioritizing cost-efficiency.",
            "RELIABLE_TRAVEL": "Highly reliable connection with strong historical performance.",
            "LEISURELY_PATH": "A long-distance journey with stable transfers for a relaxed pace.",
            "RISKY_BUT_FAST": "Fastest option available, but carries higher risk of delay today."
        }
        
        story = templates.get(best_cat, "Balanced journey across multiple train segments.")
        
        # 4. Contextual Modifiers
        if delay_penalty > 500:
            story += " Impacted by minor real-time delays."
            
        return story

journey_story_model = JourneyStoryModel()
