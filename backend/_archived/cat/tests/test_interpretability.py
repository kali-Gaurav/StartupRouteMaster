"""
Unit tests for the CAT interpretability module.

Tests:
- Attention weight extraction and aggregation
- Contributing factor ranking
- Confidence explanation generation
"""

import pytest
import torch

from backend.cat.models.transformer import create_cat_model
from backend.cat.interpretability import (
    AttentionExtractor,
    ContributingFactorAnalyzer,
    ConfidenceExplainer,
    extract_and_aggregate_attention,
    get_attention_visualization_data,
    analyze_factors_from_model,
    explain_confidence_from_model,
)
from backend.cat.interpretability.attention_extractor import AttentionWeights
from backend.cat.interpretability.contributing_factors import FactorImportance
from backend.cat.interpretability.confidence_explainer import ConfidenceExplanation


class TestAttentionExtractor:
    """Tests for AttentionExtractor class."""
    
    def test_initialization(self):
        """Test that attention extractor initializes correctly."""
        model = create_cat_model()
        extractor = AttentionExtractor(model)
        
        assert extractor.model == model
        assert extractor._last_attention_weights is None
    
    def test_extract_attention_weights(self):
        """Test that attention weights can be extracted."""
        model = create_cat_model()
        model.eval()
        
        input_dim = (
            64 +  # event_embedding_dim
            32 +  # weather_embedding_dim
            24 * 64 +  # historical_sequence_length * event_embedding_dim
            64  # temporal_encoding_dim
        )
        
        extractor = AttentionExtractor(model)
        input_tensor = torch.randn(1, input_dim)
        
        attention_weights = extractor.extract_attention_weights(input_tensor)
        
        assert isinstance(attention_weights, AttentionWeights)
        assert len(attention_weights.layer_weights) > 0
        assert attention_weights.aggregated_weights is not None
        assert attention_weights.aggregated_weights.dim() == 2
    
    def test_aggregated_weights_shape(self):
        """Test that aggregated weights have correct shape."""
        model = create_cat_model()
        model.eval()
        
        input_dim = (
            64 + 32 + 24 * 64 + 64
        )
        
        extractor = AttentionExtractor(model)
        input_tensor = torch.randn(1, input_dim)
        
        attention_weights = extractor.extract_attention_weights(input_tensor)
        
        # Aggregated weights should be [seq_len, seq_len]
        seq_len = attention_weights.aggregated_weights.shape[0]
        assert attention_weights.aggregated_weights.shape == (seq_len, seq_len)
    
    def test_aggregated_weights_sum_to_one(self):
        """Test that aggregated attention weights sum to 1."""
        model = create_cat_model()
        model.eval()
        
        input_dim = (
            64 + 32 + 24 * 64 + 64
        )
        
        extractor = AttentionExtractor(model)
        input_tensor = torch.randn(1, input_dim)
        
        attention_weights = extractor.extract_attention_weights(input_tensor)
        
        # Check that weights sum to 1 along the attention dimension
        weight_sums = attention_weights.aggregated_weights.sum(dim=-1)
        assert torch.allclose(weight_sums, torch.ones_like(weight_sums), atol=1e-5)
    
    def test_no_nan_in_weights(self):
        """Test that attention weights don't contain NaN values."""
        model = create_cat_model()
        model.eval()
        
        input_dim = (
            64 + 32 + 24 * 64 + 64
        )
        
        extractor = AttentionExtractor(model)
        input_tensor = torch.randn(1, input_dim)
        
        attention_weights = extractor.extract_attention_weights(input_tensor)
        
        for layer_weights in attention_weights.layer_weights:
            assert not torch.isnan(layer_weights).any()
        
        assert not torch.isnan(attention_weights.aggregated_weights).any()
    
    def test_get_last_attention_weights(self):
        """Test that last attention weights can be retrieved."""
        model = create_cat_model()
        model.eval()
        
        input_dim = (
            64 + 32 + 24 * 64 + 64
        )
        
        extractor = AttentionExtractor(model)
        input_tensor = torch.randn(1, input_dim)
        
        # Extract weights
        extractor.extract_attention_weights(input_tensor)
        
        # Get last weights
        last_weights = extractor.get_last_attention_weights()
        
        assert last_weights is not None
        assert isinstance(last_weights, AttentionWeights)
    
    def test_validate_attention_weights(self):
        """Test attention weight validation."""
        model = create_cat_model()
        model.eval()
        
        input_dim = (
            64 + 32 + 24 * 64 + 64
        )
        
        extractor = AttentionExtractor(model)
        input_tensor = torch.randn(1, input_dim)
        
        attention_weights = extractor.extract_attention_weights(input_tensor)
        
        # Should validate successfully
        assert extractor.validate_attention_weights(attention_weights) is True
    
    def test_extract_head_weights(self):
        """Test extraction of per-head weights."""
        model = create_cat_model()
        model.eval()
        
        input_dim = (
            64 + 32 + 24 * 64 + 64
        )
        
        extractor = AttentionExtractor(model)
        input_tensor = torch.randn(1, input_dim)
        
        attention_weights = extractor.extract_attention_weights(
            input_tensor, return_head_weights=True
        )
        
        assert attention_weights.head_weights is not None
        assert len(attention_weights.head_weights) == len(attention_weights.layer_weights)
        
        # Each layer should have num_heads weights
        num_heads = model.num_heads
        for layer_head_weights in attention_weights.head_weights:
            assert len(layer_head_weights) == num_heads


class TestContributingFactorAnalyzer:
    """Tests for ContributingFactorAnalyzer class."""
    
    def test_initialization(self):
        """Test that analyzer initializes correctly."""
        model = create_cat_model()
        extractor = AttentionExtractor(model)
        analyzer = ContributingFactorAnalyzer(extractor)
        
        assert analyzer.attention_extractor == extractor
        assert analyzer._last_analysis is None
    
    def test_analyze_contributing_factors(self):
        """Test that contributing factors can be analyzed."""
        model = create_cat_model()
        model.eval()
        
        input_dim = (
            64 + 32 + 24 * 64 + 64
        )
        
        extractor = AttentionExtractor(model)
        input_tensor = torch.randn(1, input_dim)
        
        attention_weights = extractor.extract_attention_weights(input_tensor)
        
        analyzer = ContributingFactorAnalyzer(extractor)
        factor_importance = analyzer.analyze_contributing_factors(attention_weights)
        
        assert len(factor_importance) > 0
        assert isinstance(factor_importance[0], FactorImportance)
    
    def test_factor_importance_sorted(self):
        """Test that factors are sorted by importance."""
        model = create_cat_model()
        model.eval()
        
        input_dim = (
            64 + 32 + 24 * 64 + 64
        )
        
        extractor = AttentionExtractor(model)
        input_tensor = torch.randn(1, input_dim)
        
        attention_weights = extractor.extract_attention_weights(input_tensor)
        
        analyzer = ContributingFactorAnalyzer(extractor)
        factor_importance = analyzer.analyze_contributing_factors(attention_weights)
        
        # Check that factors are sorted by importance (descending)
        for i in range(len(factor_importance) - 1):
            assert factor_importance[i].importance_score >= factor_importance[i + 1].importance_score
    
    def test_factor_importance_normalized(self):
        """Test that factor importance scores sum to 1."""
        model = create_cat_model()
        model.eval()
        
        input_dim = (
            64 + 32 + 24 * 64 + 64
        )
        
        extractor = AttentionExtractor(model)
        input_tensor = torch.randn(1, input_dim)
        
        attention_weights = extractor.extract_attention_weights(input_tensor)
        
        analyzer = ContributingFactorAnalyzer(extractor)
        factor_importance = analyzer.analyze_contributing_factors(attention_weights)
        
        # Check that scores sum to approximately 1
        total = sum(f.importance_score for f in factor_importance)
        assert abs(total - 1.0) < 0.01
    
    def test_to_contributing_factors(self):
        """Test conversion to ContributingFactor schema."""
        model = create_cat_model()
        model.eval()
        
        input_dim = (
            64 + 32 + 24 * 64 + 64
        )
        
        extractor = AttentionExtractor(model)
        input_tensor = torch.randn(1, input_dim)
        
        attention_weights = extractor.extract_attention_weights(input_tensor)
        
        analyzer = ContributingFactorAnalyzer(extractor)
        factor_importance = analyzer.analyze_contributing_factors(attention_weights)
        
        contributing_factors = analyzer.to_contributing_factors(factor_importance)
        
        assert len(contributing_factors) > 0
        # Check that factors have the expected attributes
        assert all(hasattr(f, 'factor_name') for f in contributing_factors)
        assert all(hasattr(f, 'importance_score') for f in contributing_factors)
        assert all(hasattr(f, 'description') for f in contributing_factors)
    
    def test_get_factor_ranking(self):
        """Test getting factor ranking as tuples."""
        model = create_cat_model()
        model.eval()
        
        input_dim = (
            64 + 32 + 24 * 64 + 64
        )
        
        extractor = AttentionExtractor(model)
        input_tensor = torch.randn(1, input_dim)
        
        attention_weights = extractor.extract_attention_weights(input_tensor)
        
        analyzer = ContributingFactorAnalyzer(extractor)
        analyzer.analyze_contributing_factors(attention_weights)
        
        ranking = analyzer.get_factor_ranking()
        
        assert len(ranking) > 0
        assert all(isinstance(item, tuple) for item in ranking)
        assert all(len(item) == 3 for item in ranking)
    
    def test_get_last_analysis(self):
        """Test that last analysis can be retrieved."""
        model = create_cat_model()
        model.eval()
        
        input_dim = (
            64 + 32 + 24 * 64 + 64
        )
        
        extractor = AttentionExtractor(model)
        input_tensor = torch.randn(1, input_dim)
        
        attention_weights = extractor.extract_attention_weights(input_tensor)
        
        analyzer = ContributingFactorAnalyzer(extractor)
        analyzer.analyze_contributing_factors(attention_weights)
        
        last_analysis = analyzer.get_last_analysis()
        
        assert last_analysis is not None
        assert len(last_analysis) > 0


class TestConfidenceExplainer:
    """Tests for ConfidenceExplainer class."""
    
    def test_initialization(self):
        """Test that explainer initializes correctly."""
        explainer = ConfidenceExplainer()
        
        assert explainer.attention_extractor is None
        assert explainer.factor_analyzer is None
        assert explainer._last_explanation is None
    
    def test_explain_confidence(self):
        """Test that confidence explanation can be generated."""
        model = create_cat_model()
        model.eval()
        
        input_dim = (
            64 + 32 + 24 * 64 + 64
        )
        
        input_tensor = torch.randn(1, input_dim)
        
        with torch.no_grad():
            output = model(input_tensor)
        
        confidence_lower = output["confidence_lower"].item()
        confidence_upper = output["confidence_upper"].item()
        
        explainer = ConfidenceExplainer()
        explanation = explainer.explain_confidence(
            confidence_lower=confidence_lower,
            confidence_upper=confidence_upper,
            context_info={"event_count": 2, "weather_severity": 3}
        )
        
        assert isinstance(explanation, ConfidenceExplanation)
        assert 0.0 <= explanation.confidence_level <= 1.0
        assert len(explanation.explanation) > 0
    
    def test_confidence_categorization(self):
        """Test confidence level categorization."""
        explainer = ConfidenceExplainer()
        
        # Test different confidence levels
        test_cases = [
            (0.95, "very_high"),
            (0.85, "high"),
            (0.6, "moderate"),
            (0.4, "low"),
            (0.15, "very_low"),
        ]
        
        for confidence_level, expected_category in test_cases:
            explanation = explainer.explain_confidence(
                confidence_lower=confidence_level - 0.05,
                confidence_upper=confidence_level + 0.05
            )
            
            assert explanation.confidence_category == expected_category
    
    def test_uncertainty_factors(self):
        """Test uncertainty factor analysis."""
        model = create_cat_model()
        model.eval()
        
        input_dim = (
            64 + 32 + 24 * 64 + 64
        )
        
        input_tensor = torch.randn(1, input_dim)
        
        with torch.no_grad():
            output = model(input_tensor)
        
        confidence_lower = output["confidence_lower"].item()
        confidence_upper = output["confidence_upper"].item()
        
        explainer = ConfidenceExplainer()
        explanation = explainer.explain_confidence(
            confidence_lower=confidence_lower,
            confidence_upper=confidence_upper,
            context_info={"event_count": 0, "weather_severity": 0}
        )
        
        # Should have some uncertainty factors
        assert isinstance(explanation.uncertainty_factors, list)
    
    def test_recommendations(self):
        """Test recommendation generation."""
        model = create_cat_model()
        model.eval()
        
        input_dim = (
            64 + 32 + 24 * 64 + 64
        )
        
        input_tensor = torch.randn(1, input_dim)
        
        with torch.no_grad():
            output = model(input_tensor)
        
        confidence_lower = output["confidence_lower"].item()
        confidence_upper = output["confidence_upper"].item()
        
        explainer = ConfidenceExplainer()
        explanation = explainer.explain_confidence(
            confidence_lower=confidence_lower,
            confidence_upper=confidence_upper
        )
        
        # Should have recommendations
        assert isinstance(explanation.recommendations, list)
        assert len(explanation.recommendations) >= 0
    
    def test_format_explanation_for_display(self):
        """Test formatted explanation for display."""
        model = create_cat_model()
        model.eval()
        
        input_dim = (
            64 + 32 + 24 * 64 + 64
        )
        
        input_tensor = torch.randn(1, input_dim)
        
        with torch.no_grad():
            output = model(input_tensor)
        
        confidence_lower = output["confidence_lower"].item()
        confidence_upper = output["confidence_upper"].item()
        
        explainer = ConfidenceExplainer()
        explanation = explainer.explain_confidence(
            confidence_lower=confidence_lower,
            confidence_upper=confidence_upper
        )
        
        formatted = explainer.format_explanation_for_display(explanation)
        
        assert isinstance(formatted, str)
        assert "Confidence Level:" in formatted
        assert "Category:" in formatted
        assert "Explanation:" in formatted
    
    def test_get_last_explanation(self):
        """Test that last explanation can be retrieved."""
        model = create_cat_model()
        model.eval()
        
        input_dim = (
            64 + 32 + 24 * 64 + 64
        )
        
        input_tensor = torch.randn(1, input_dim)
        
        with torch.no_grad():
            output = model(input_tensor)
        
        confidence_lower = output["confidence_lower"].item()
        confidence_upper = output["confidence_upper"].item()
        
        explainer = ConfidenceExplainer()
        explainer.explain_confidence(
            confidence_lower=confidence_lower,
            confidence_upper=confidence_upper
        )
        
        last_explanation = explainer.get_last_explanation()
        
        assert last_explanation is not None
        assert isinstance(last_explanation, ConfidenceExplanation)


class TestConvenienceFunctions:
    """Tests for convenience functions."""
    
    def test_extract_and_aggregate_attention(self):
        """Test extract_and_aggregate_attention convenience function."""
        model = create_cat_model()
        model.eval()
        
        input_dim = (
            64 + 32 + 24 * 64 + 64
        )
        
        input_tensor = torch.randn(1, input_dim)
        
        aggregated, layer_weights = extract_and_aggregate_attention(model, input_tensor)
        
        assert isinstance(aggregated, torch.Tensor)
        assert isinstance(layer_weights, list)
        assert len(layer_weights) > 0
    
    def test_get_attention_visualization_data(self):
        """Test get_attention_visualization_data convenience function."""
        model = create_cat_model()
        model.eval()
        
        input_dim = (
            64 + 32 + 24 * 64 + 64
        )
        
        input_tensor = torch.randn(1, input_dim)
        
        viz_data = get_attention_visualization_data(model, input_tensor)
        
        assert isinstance(viz_data, dict)
        assert "layer_weights" in viz_data
        assert "aggregated" in viz_data
        assert "head_weights" in viz_data
    
    def test_analyze_factors_from_model(self):
        """Test analyze_factors_from_model convenience function."""
        model = create_cat_model()
        model.eval()
        
        input_dim = (
            64 + 32 + 24 * 64 + 64
        )
        
        input_tensor = torch.randn(1, input_dim)
        
        factors = analyze_factors_from_model(model, input_tensor)
        
        assert isinstance(factors, list)
        assert len(factors) > 0
        assert all(hasattr(f, 'factor_name') for f in factors)
    
    def test_explain_confidence_from_model(self):
        """Test explain_confidence_from_model convenience function."""
        model = create_cat_model()
        model.eval()
        
        input_dim = (
            64 + 32 + 24 * 64 + 64
        )
        
        input_tensor = torch.randn(1, input_dim)
        
        with torch.no_grad():
            output = model(input_tensor)
        
        confidence_lower = output["confidence_lower"].item()
        confidence_upper = output["confidence_upper"].item()
        
        explanation = explain_confidence_from_model(
            model, input_tensor, confidence_lower, confidence_upper
        )
        
        assert isinstance(explanation, ConfidenceExplanation)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
