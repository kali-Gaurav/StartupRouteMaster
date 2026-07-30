"""Interpretability module for the Contextual Availability Transformer (CAT) system."""

from .attention_extractor import (
    AttentionExtractor, 
    AttentionWeights,
    extract_and_aggregate_attention,
    get_attention_visualization_data
)
from .contributing_factors import (
    ContributingFactorAnalyzer, 
    FactorImportance,
    analyze_factors_from_model
)
from .confidence_explainer import (
    ConfidenceExplainer, 
    ConfidenceExplanation,
    explain_confidence_from_model
)

__all__ = [
    "AttentionExtractor",
    "AttentionWeights",
    "ContributingFactorAnalyzer",
    "ConfidenceExplainer",
    "FactorImportance",
    "ConfidenceExplanation",
    "extract_and_aggregate_attention",
    "get_attention_visualization_data",
    "analyze_factors_from_model",
    "explain_confidence_from_model",
]
