import logging
import asyncio
from typing import List, Dict, Any, Optional
from services.agents.base_agent import BaseAgent, AgentPriority

logger = logging.getLogger("agent.narrator")

class NarratorAgent(BaseAgent):
    """
    [G3.1.1] The 'Narrator' Why-THIS-Route Agent.
    Intelligent Explainability Layer: Converts complex scoring signals into 
    persuasive, human-readable narratives to increase user trust and conversion.
    """
    name = "NarratorAgent"
    description = "Translates route scoring signals into human-readable explainability narratives."
    category = "intelligence"
    priority = AgentPriority.NORMAL
    icon = "🎙️"
    color = "#8B5CF6" # Violet

    def __init__(self):
        super().__init__()
        # Persona mapping for different 'Voices'
        self.personas = {
            "business": "Efficient and fact-based. Focus on time saved and reliability.",
            "family": "Warm and safety-oriented. Focus on comfort, security, and directness.",
            "budget": "Helpful and value-oriented. Focus on money saved and optimization."
        }

    async def narrate_route(self, route_data: Dict[str, Any], persona: str = "business") -> str:
        """
        [Child G3.1.1.1 & G3.1.1.2]
        Generates a natural language explanation for why this route was selected.
        """
        # 1. Rank Signals (Child G3.1.1.1)
        signals = self._rank_signals(route_data)
        
        # 2. Generate Narrative (Child G3.1.1.2)
        # In a production system, this would call an LLM (Gemini/GPT).
        # We implement a high-intelligence template engine with LLM hooks.
        narrative = await self._generate_intelligent_explanation(signals, persona, route_data)
        
        return narrative

    def _rank_signals(self, route: Dict[str, Any]) -> List[Dict[str, Any]]:
        """
        Identifies the 'Wowy' factors of a route.
        """
        signals = []
        
        # Availability (Crucial for Tatkal/Rush)
        prob = route.get("availability_prob", 0.0)
        if prob > 0.8:
            signals.append({"type": "availability", "score": prob, "label": "High Confidence Availability"})
        
        # Speed/Time
        duration = route.get("total_duration_mins", 0)
        avg_duration = route.get("avg_route_duration_mins", 600)
        if duration < avg_duration * 0.8:
            savings = avg_duration - duration
            signals.append({"type": "speed", "score": 1.0, "label": f"Saves {savings} mins"})
            
        # Safety (Cluster Anomaly Check)
        risk = route.get("risk_score", 0.5)
        if risk < 0.2:
            signals.append({"type": "safety", "score": 1.0 - risk, "label": "Top-Tier Safety Rating"})

        # value
        value = route.get("value_score", 0.0)
        if value > 0.7:
             signals.append({"type": "value", "score": value, "label": "Exceptional Value"})

        # Sort by impact
        signals.sort(key=lambda x: x["score"], reverse=True)
        return signals

    async def _generate_intelligent_explanation(self, signals: List[Dict[str, Any]], persona: str, route: Dict[str, Any]) -> str:
        """
        Linguistic Personality Engine (Child G3.1.1.2).
        """
        if not signals:
            return "This route is a balanced option for your journey."

        primary = signals[0]
        secondary = signals[1] if len(signals) > 1 else None
        
        train_name = route.get("train_name", "this connection")
        
        # Base narrations based on persona
        if persona == "family":
            text = f"I've highlighted {train_name} for you because "
            if primary["type"] == "safety":
                text += "it has our highest safety rating, ensuring a secure and comfortable journey for your loved ones."
            elif primary["type"] == "availability":
                 text += "it has the best confirmed-seat probability, so you can travel without waitlist stress."
            else:
                 text += f"it's a very reliable choice, specifically chosen for its {primary['label'].lower()}."
        
        elif persona == "budget":
            text = f"Great find! {train_name} stands out for its {primary['label'].lower()}."
            if secondary:
                text += f" Plus, you're also getting {secondary['label'].lower()}."
        
        else: # business
            text = f"Optimized Path: {train_name} selected for {primary['label'].lower()}."
            if secondary:
                text += f" Secondary Factor: {secondary['label'].lower()}."

        # [G3.3.1] Predictive Sentiment Advice Injection
        try:
            from services.ml.price_sentiment_model import price_sentiment_model
            src = route.get("source_code", "SRC")
            dst = route.get("destination_code", "DST")
            sentiment = await price_sentiment_model.get_route_sentiment(src, dst)
            
            if sentiment["sentiment"] != "STABLE":
                text += f" 📈 Advisory: {sentiment['advice']}"
        except Exception as e:
            logger.error(f"Sentiment injection failed: {e}")

        return text

    async def explain_search_results(self, results: List[Dict[str, Any]], persona: str = "business") -> List[Dict[str, Any]]:
        """
        [Child G3.1.1.3]
        Enriches a batch of search results with narratives.
        """
        for route in results:
            route["narrative"] = await self.narrate_route(route, persona)
        return results

narrator_agent = NarratorAgent()
