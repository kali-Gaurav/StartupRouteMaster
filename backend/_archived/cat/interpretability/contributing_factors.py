"""
Contributing factor analysis for the CAT system.

This module provides functionality to:
- Analyze attention patterns to identify important factors
- Compute importance scores for events, weather, history
- Generate ranked list of contributing factors
- Map attention patterns to interpretable factor names
"""

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import torch
from torch import Tensor

from ..models.schemas import ContributingFactor
from .attention_extractor import AttentionExtractor, AttentionWeights


@dataclass
class FactorImportance:
    """
    Container for factor importance analysis results.
    
    Attributes:
        factor_name: Name of the factor
        importance_score: Importance score in range [0, 1]
        description: Human-readable description
        attention_contribution: How much attention this factor received
        position_weights: Attention weights for each position
    """
    factor_name: str
    importance_score: float
    description: str
    attention_contribution: float
    position_weights: Optional[Tensor] = None


class ContributingFactorAnalyzer:
    """
    Analyzes attention patterns to identify contributing factors.
    
    This class maps attention weights to interpretable factors such as:
    - Event impact (attention to event-related positions)
    - Weather impact (attention to weather-related positions)
    - Historical pattern (attention to historical sequence positions)
    - Temporal pattern (attention to temporal encoding positions)
    - Location context (attention to location-related features)
    """
    
    # Factor categories with their descriptions
    FACTOR_CATEGORIES = {
        "event_impact": "Attention to event calendar data",
        "weather_impact": "Attention to weather conditions",
        "historical_pattern": "Attention to historical availability patterns",
        "temporal_pattern": "Attention to temporal encodings",
        "location_context": "Attention to location-specific features",
    }
    
    def __init__(self, attention_extractor: AttentionExtractor = None):
        """
        Initialize the contributing factor analyzer.
        
        Args:
            attention_extractor: Optional AttentionExtractor instance
        """
        self.attention_extractor = attention_extractor
        self._last_analysis: Optional[List[FactorImportance]] = None
    
    def analyze_contributing_factors(
        self,
        attention_weights: AttentionWeights,
        input_features: Optional[Tensor] = None,
        feature_names: List[str] = None
    ) -> List[FactorImportance]:
        """
        Analyze attention patterns to identify important factors.
        
        Args:
            attention_weights: AttentionWeights object from extraction
            input_features: Optional input tensor for feature-level analysis
            feature_names: Optional list of feature names
            
        Returns:
            List of FactorImportance objects sorted by importance
        """
        # Get aggregated attention weights
        aggregated = attention_weights.aggregated_weights
        # aggregated: [seq_len, seq_len]
        
        # Analyze attention patterns
        # Higher attention to certain positions indicates importance
        importance = self._analyze_attention_patterns(aggregated)
        
        # Map importance to factor categories
        factor_importance = self._map_to_factors(importance, feature_names)
        
        # Store for later retrieval
        self._last_analysis = factor_importance
        
        return factor_importance
    
    def _analyze_attention_patterns(self, aggregated: Tensor) -> Tensor:
        """
        Analyze attention patterns to compute importance scores.
        
        Args:
            aggregated: Aggregated attention weights [seq_len, seq_len]
            
        Returns:
            Importance scores for each position [seq_len]
        """
        # Mean attention received by each position (column-wise)
        # This indicates how much each position is "attended to"
        attention_received = aggregated.mean(dim=0)  # [seq_len]
        
        # Mean attention given by each position (row-wise)
        # This indicates how much each position "attends to others"
        attention_given = aggregated.mean(dim=1)  # [seq_len]
        
        # Combined importance: both receiving and giving attention
        importance = (attention_received + attention_given) / 2
        
        # Normalize to [0, 1]
        importance = self._normalize_scores(importance)
        
        return importance
    
    def _normalize_scores(self, scores: Tensor) -> Tensor:
        """
        Normalize scores to [0, 1] range.
        
        Args:
            scores: Raw importance scores
            
        Returns:
            Normalized scores in [0, 1]
        """
        min_score = scores.min()
        max_score = scores.max()
        
        if max_score - min_score < 1e-8:
            # All scores are approximately equal
            return torch.ones_like(scores) / len(scores)
        
        normalized = (scores - min_score) / (max_score - min_score)
        
        return normalized
    
    def _map_to_factors(
        self,
        importance: Tensor,
        feature_names: List[str] = None
    ) -> List[FactorImportance]:
        """
        Map importance scores to interpretable factor categories.
        
        Args:
            importance: Normalized importance scores [seq_len]
            feature_names: Optional list of feature names
            
        Returns:
            List of FactorImportance objects
        """
        num_factors = len(self.FACTOR_CATEGORIES)
        seq_len = len(importance)
        
        # Distribute importance across factor categories
        # Each factor category gets a portion of the total importance
        factor_scores = []
        
        for i, (factor_name, description) in enumerate(self.FACTOR_CATEGORIES.items()):
            # Assign importance based on position in sequence
            # This is a simplified mapping - in practice, you'd use feature names
            # or domain knowledge to map positions to factors
            
            # Get importance for this factor's positions
            start_idx = (i * seq_len) // num_factors
            end_idx = ((i + 1) * seq_len) // num_factors
            
            if end_idx <= start_idx:
                end_idx = start_idx + 1
            
            factor_importance = importance[start_idx:end_idx].mean().item()
            
            factor_scores.append(FactorImportance(
                factor_name=factor_name,
                importance_score=factor_importance,
                description=description,
                attention_contribution=factor_importance,
                position_weights=importance[start_idx:end_idx]
            ))
        
        # Sort by importance score (descending)
        factor_scores.sort(key=lambda x: x.importance_score, reverse=True)
        
        # Renormalize scores to sum to 1
        total = sum(f.importance_score for f in factor_scores)
        if total > 0:
            for f in factor_scores:
                f.importance_score /= total
        
        return factor_scores
    
    def to_contributing_factors(
        self,
        factor_importance: List[FactorImportance] = None
    ) -> List[ContributingFactor]:
        """
        Convert FactorImportance objects to ContributingFactor schema objects.
        
        Args:
            factor_importance: List of FactorImportance objects (uses last analysis if None)
            
        Returns:
            List of ContributingFactor objects
        """
        if factor_importance is None:
            factor_importance = self._last_analysis
        
        if factor_importance is None:
            return []
        
        contributing_factors = []
        for fi in factor_importance:
            contributing_factors.append(ContributingFactor(
                factor_name=fi.factor_name,
                importance_score=fi.importance_score,
                description=fi.description
            ))
        
        return contributing_factors
    
    def get_last_analysis(self) -> Optional[List[FactorImportance]]:
        """Get the last factor importance analysis."""
        return self._last_analysis
    
    def get_factor_ranking(
        self,
        factor_importance: List[FactorImportance] = None
    ) -> List[Tuple[str, float, str]]:
        """
        Get a ranked list of contributing factors.
        
        Args:
            factor_importance: List of FactorImportance objects (uses last analysis if None)
            
        Returns:
            List of tuples (factor_name, importance_score, description)
        """
        if factor_importance is None:
            factor_importance = self._last_analysis
        
        if factor_importance is None:
            return []
        
        return [
            (fi.factor_name, fi.importance_score, fi.description)
            for fi in factor_importance
        ]


def analyze_factors_from_model(
    model,
    input_tensor: Tensor,
    attention_extractor: AttentionExtractor = None
) -> List[ContributingFactor]:
    """
    Convenience function to analyze contributing factors from model inference.
    
    Args:
        model: The CAT model
        input_tensor: Input tensor [batch_size, input_dim]
        attention_extractor: Optional AttentionExtractor instance
        
    Returns:
        List of ContributingFactor objects
    """
    if attention_extractor is None:
        attention_extractor = AttentionExtractor(model)
    
    # Extract attention weights
    attention_weights = attention_extractor.extract_attention_weights(input_tensor)
    
    # Analyze contributing factors
    analyzer = ContributingFactorAnalyzer(attention_extractor)
    factor_importance = analyzer.analyze_contributing_factors(attention_weights)
    
    # Convert to ContributingFactor schema
    return analyzer.to_contributing_factors(factor_importance)
