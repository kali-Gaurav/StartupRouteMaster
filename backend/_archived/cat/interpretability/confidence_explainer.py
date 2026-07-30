"""
Confidence explanation for the CAT system.

This module provides functionality to:
- Explain prediction uncertainty in terms of contributing factors
- Generate human-readable explanation of low confidence
- Identify which contextual factors contribute to uncertainty
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import torch
from torch import Tensor

from ..models.schemas import ContributingFactor
from .attention_extractor import AttentionExtractor
from .contributing_factors import ContributingFactorAnalyzer


@dataclass
class ConfidenceExplanation:
    """
    Container for confidence explanation results.
    
    Attributes:
        confidence_level: The confidence level (0-1)
        explanation: Human-readable explanation
        uncertainty_factors: List of factors contributing to uncertainty
        confidence_category: Category of confidence level
        recommendations: Suggested actions based on confidence
    """
    confidence_level: float
    explanation: str
    uncertainty_factors: List[Dict[str, any]]
    confidence_category: str
    recommendations: List[str]


class ConfidenceExplainer:
    """
    Generates human-readable explanations for prediction confidence.
    
    This class analyzes:
    - Overall confidence level
    - Which factors contribute to uncertainty
    - Contextual information about the prediction
    - Actionable recommendations based on confidence
    """
    
    # Confidence level categories
    CONFIDENCE_CATEGORIES = {
        "very_high": (0.9, 1.0, "Very High"),
        "high": (0.7, 0.9, "High"),
        "moderate": (0.5, 0.7, "Moderate"),
        "low": (0.3, 0.5, "Low"),
        "very_low": (0.0, 0.3, "Very Low"),
    }
    
    # Factor names that typically affect confidence
    UNCERTAINTY_FACTORS = {
        "event_impact": "Event data",
        "weather_impact": "Weather conditions",
        "historical_pattern": "Historical patterns",
        "temporal_pattern": "Temporal patterns",
        "location_context": "Location context",
    }
    
    def __init__(
        self,
        attention_extractor: AttentionExtractor = None,
        factor_analyzer: ContributingFactorAnalyzer = None
    ):
        """
        Initialize the confidence explainer.
        
        Args:
            attention_extractor: Optional AttentionExtractor instance
            factor_analyzer: Optional ContributingFactorAnalyzer instance
        """
        self.attention_extractor = attention_extractor
        self.factor_analyzer = factor_analyzer
        self._last_explanation: Optional[ConfidenceExplanation] = None
    
    def explain_confidence(
        self,
        confidence_lower: float,
        confidence_upper: float,
        contributing_factors: List[ContributingFactor] = None,
        attention_weights = None,
        context_info: Dict[str, any] = None
    ) -> ConfidenceExplanation:
        """
        Generate a human-readable explanation for prediction confidence.
        
        Args:
            confidence_lower: Lower bound of confidence interval
            confidence_upper: Upper bound of confidence interval
            contributing_factors: List of ContributingFactor objects
            attention_weights: Optional attention weights for additional analysis
            context_info: Optional dictionary with contextual information
            
        Returns:
            ConfidenceExplanation object with explanation and recommendations
        """
        # Calculate average confidence
        confidence_level = (confidence_lower + confidence_upper) / 2
        
        # Determine confidence category
        confidence_category = self._categorize_confidence(confidence_level)
        
        # Analyze uncertainty factors
        uncertainty_factors = self._analyze_uncertainty_factors(
            confidence_level, contributing_factors, attention_weights
        )
        
        # Generate explanation
        explanation = self._generate_explanation(
            confidence_level, confidence_category, uncertainty_factors, context_info
        )
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            confidence_level, confidence_category, uncertainty_factors
        )
        
        confidence_explanation = ConfidenceExplanation(
            confidence_level=confidence_level,
            explanation=explanation,
            uncertainty_factors=uncertainty_factors,
            confidence_category=confidence_category,
            recommendations=recommendations
        )
        
        # Store for later retrieval
        self._last_explanation = confidence_explanation
        
        return confidence_explanation
    
    def _categorize_confidence(self, confidence_level: float) -> str:
        """
        Categorize confidence level into predefined categories.
        
        Args:
            confidence_level: Confidence level in [0, 1]
            
        Returns:
            Category name (very_high, high, moderate, low, very_low)
        """
        for category, (lower, upper, _) in self.CONFIDENCE_CATEGORIES.items():
            if lower <= confidence_level <= upper:
                return category
        
        # Fallback
        return "moderate"
    
    def _analyze_uncertainty_factors(
        self,
        confidence_level: float,
        contributing_factors: List[ContributingFactor] = None,
        attention_weights = None
    ) -> List[Dict[str, any]]:
        """
        Analyze which factors contribute to uncertainty.
        
        Args:
            confidence_level: Overall confidence level
            contributing_factors: List of ContributingFactor objects
            attention_weights: Optional attention weights
            
        Returns:
            List of uncertainty factor dictionaries
        """
        uncertainty_factors = []
        
        # If we have contributing factors, analyze them
        if contributing_factors:
            for factor in contributing_factors:
                # Low confidence factors are those with moderate importance
                # (very high or very low importance might indicate certainty)
                importance = factor.importance_score
                
                # Factor contributes to uncertainty if:
                # - It has moderate importance (0.2-0.6)
                # - And confidence is low
                if confidence_level < 0.7 and 0.2 <= importance <= 0.6:
                    uncertainty_factors.append({
                        "factor_name": factor.factor_name,
                        "importance_score": importance,
                        "contribution": "moderate_uncertainty",
                        "description": f"{factor.factor_name} has moderate influence"
                    })
                
                # Very low importance might also indicate uncertainty
                elif confidence_level < 0.5 and importance < 0.15:
                    uncertainty_factors.append({
                        "factor_name": factor.factor_name,
                        "importance_score": importance,
                        "contribution": "low_signal",
                        "description": f"{factor.factor_name} has very low signal"
                    })
        
        # If attention weights are available, analyze attention patterns
        if attention_weights is not None and hasattr(attention_weights, 'aggregated_weights'):
            # Analyze attention entropy (higher entropy = more uncertainty)
            aggregated = attention_weights.aggregated_weights
            
            # Mean attention variance across positions
            attention_variance = aggregated.var(dim=0).mean().item()
            
            if attention_variance > 0.1 and confidence_level < 0.6:
                uncertainty_factors.append({
                    "factor_name": "attention_entropy",
                    "importance_score": attention_variance,
                    "contribution": "high_entropy",
                    "description": "Attention distribution is highly variable"
                })
        
        # Sort by contribution severity
        uncertainty_factors.sort(
            key=lambda x: self._contribution_severity(x["contribution"]),
            reverse=True
        )
        
        return uncertainty_factors
    
    def _contribution_severity(self, contribution: str) -> int:
        """
        Get severity score for a contribution type.
        
        Args:
            contribution: Contribution type string
            
        Returns:
            Severity score (higher = more severe)
        """
        severity_map = {
            "high_entropy": 3,
            "moderate_uncertainty": 2,
            "low_signal": 1,
        }
        return severity_map.get(contribution, 0)
    
    def _generate_explanation(
        self,
        confidence_level: float,
        confidence_category: str,
        uncertainty_factors: List[Dict[str, any]],
        context_info: Dict[str, any] = None
    ) -> str:
        """
        Generate a human-readable explanation.
        
        Args:
            confidence_level: Overall confidence level
            confidence_category: Category of confidence
            uncertainty_factors: List of uncertainty factors
            context_info: Optional contextual information
            
        Returns:
            Human-readable explanation string
        """
        # Start with confidence level description
        category_names = {
            "very_high": "very high",
            "high": "high",
            "moderate": "moderate",
            "low": "low",
            "very_low": "very low",
        }
        
        explanation = f"The model has {category_names.get(confidence_category, 'moderate')} confidence "
        explanation += f"in this prediction (confidence level: {confidence_level:.1%})."
        
        # Add context information if available
        if context_info:
            if "event_count" in context_info:
                event_count = context_info["event_count"]
                if event_count > 0:
                    explanation += f" There are {event_count} event(s) in the context."
            
            if "weather_severity" in context_info:
                weather_severity = context_info["weather_severity"]
                if weather_severity > 5:
                    explanation += f" Weather conditions are severe (severity: {weather_severity}/10)."
        
        # Add uncertainty factors
        if uncertainty_factors:
            explanation += " Key factors contributing to uncertainty:"
            
            for i, factor in enumerate(uncertainty_factors[:3]):  # Top 3 factors
                explanation += f"\n  - {factor['factor_name']}: {factor['description']}"
        
        # Add note about confidence interval
        explanation += f" The confidence interval is [lower_bound, upper_bound]."
        
        return explanation
    
    def _generate_recommendations(
        self,
        confidence_level: float,
        confidence_category: str,
        uncertainty_factors: List[Dict[str, any]]
    ) -> List[str]:
        """
        Generate actionable recommendations based on confidence.
        
        Args:
            confidence_level: Overall confidence level
            confidence_category: Category of confidence
            uncertainty_factors: List of uncertainty factors
            
        Returns:
            List of recommendation strings
        """
        recommendations = []
        
        if confidence_category in ["very_low", "low"]:
            recommendations.append(
                "Consider gathering more contextual data for this prediction"
            )
            recommendations.append(
                "Review the event calendar and weather data for accuracy"
            )
            
            if any(f["contribution"] == "high_entropy" for f in uncertainty_factors):
                recommendations.append(
                    "Consider using a more detailed historical sequence"
                )
        
        elif confidence_category == "moderate":
            recommendations.append(
                "This prediction should be used with caution"
            )
            recommendations.append(
                "Consider combining with other prediction sources"
            )
        
        elif confidence_category in ["high", "very_high"]:
            recommendations.append(
                "This prediction can be used with high confidence"
            )
            
            if confidence_category == "very_high":
                recommendations.append(
                    "Consider prioritizing this prediction in decision-making"
                )
        
        # Add specific recommendations based on uncertainty factors
        factor_recommendations = {
            "event_impact": "Verify event calendar data for accuracy",
            "weather_impact": "Check weather forecast sources",
            "historical_pattern": "Review historical data quality",
            "temporal_pattern": "Consider temporal context adjustments",
            "location_context": "Verify location-specific features",
        }
        
        for factor in uncertainty_factors:
            factor_name = factor["factor_name"]
            if factor_name in factor_recommendations:
                rec = factor_recommendations[factor_name]
                if rec not in recommendations:
                    recommendations.append(rec)
        
        return recommendations
    
    def get_last_explanation(self) -> Optional[ConfidenceExplanation]:
        """Get the last confidence explanation."""
        return self._last_explanation
    
    def format_explanation_for_display(
        self,
        confidence_explanation: ConfidenceExplanation = None
    ) -> str:
        """
        Format confidence explanation for display.
        
        Args:
            confidence_explanation: ConfidenceExplanation object (uses last if None)
            
        Returns:
            Formatted string for display
        """
        if confidence_explanation is None:
            confidence_explanation = self._last_explanation
        
        if confidence_explanation is None:
            return "No confidence explanation available."
        
        lines = [
            f"## Confidence Explanation",
            f"",
            f"**Confidence Level:** {confidence_explanation.confidence_level:.1%}",
            f"**Category:** {confidence_explanation.confidence_category.replace('_', ' ').title()}",
            f"",
            f"**Explanation:**",
            f"{confidence_explanation.explanation}",
            f"",
            f"**Uncertainty Factors:**",
        ]
        
        for factor in confidence_explanation.uncertainty_factors:
            lines.append(
                f"- {factor['factor_name']}: {factor['description']} "
                f"({factor['contribution']})"
            )
        
        if confidence_explanation.recommendations:
            lines.append("")
            lines.append("**Recommendations:**")
            for rec in confidence_explanation.recommendations:
                lines.append(f"- {rec}")
        
        return "\n".join(lines)


def explain_confidence_from_model(
    model,
    input_tensor: Tensor,
    confidence_lower: float,
    confidence_upper: float,
    attention_extractor: AttentionExtractor = None,
    factor_analyzer: ContributingFactorAnalyzer = None
) -> ConfidenceExplanation:
    """
    Convenience function to explain confidence from model inference.
    
    Args:
        model: The CAT model
        input_tensor: Input tensor [batch_size, input_dim]
        confidence_lower: Lower bound of confidence interval
        confidence_upper: Upper bound of confidence interval
        attention_extractor: Optional AttentionExtractor instance
        factor_analyzer: Optional ContributingFactorAnalyzer instance
        
    Returns:
        ConfidenceExplanation object
    """
    if attention_extractor is None:
        attention_extractor = AttentionExtractor(model)
    
    if factor_analyzer is None:
        factor_analyzer = ContributingFactorAnalyzer(attention_extractor)
    
    # Extract attention weights
    attention_weights = attention_extractor.extract_attention_weights(input_tensor)
    
    # Analyze contributing factors
    factor_importance = factor_analyzer.analyze_contributing_factors(attention_weights)
    contributing_factors = factor_analyzer.to_contributing_factors(factor_importance)
    
    # Generate confidence explanation
    explainer = ConfidenceExplainer(attention_extractor, factor_analyzer)
    explanation = explainer.explain_confidence(
        confidence_lower=confidence_lower,
        confidence_upper=confidence_upper,
        contributing_factors=contributing_factors,
        attention_weights=attention_weights
    )
    
    return explanation
