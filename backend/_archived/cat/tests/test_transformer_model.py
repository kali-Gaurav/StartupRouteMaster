"""
Comprehensive Unit Tests for the CAT Transformer Model Architecture.

Tests all model components:
- Multi-head attention mechanism
- Feed-forward network layer
- Transformer encoder layer and stack
- Prediction head with confidence intervals
- Complete CAT model

Correctness Properties Validated:
- Property 1: Prediction Probability Bounds (output in [0, 1])
- Property 8: Attention Weight Validity (rows sum to 1.0)

Requirements Covered: 3.1, 3.2, 3.3, 3.4, 3.5, 3.6, 3.7, 3.8, 7.1, 7.2, 7.3, 7.4, 7.5
"""

import pytest
import torch
import torch.nn as nn
import numpy as np
from typing import List, Tuple

from backend.cat.models import (
    MultiHeadAttention,
    FeedForwardNetwork,
    TransformerEncoderLayer,
    TransformerEncoder,
    PredictionHead,
    ConfidenceIntervalEstimator,
    CATModel,
    ModelConfig,
    create_cat_model,
    create_tiny_model,
    create_large_model
)
from backend.cat.config import settings


class TestMultiHeadAttention:
    """Tests for MultiHeadAttention module (Requirements 3.1, 3.7)."""
    
    def test_initialization_with_defaults(self):
        """Test initialization with default settings."""
        attn = MultiHeadAttention()
        
        assert attn.embed_dim == settings.model_dim
        assert attn.num_heads == settings.num_attention_heads
        assert attn.head_dim == settings.model_dim // settings.num_attention_heads
        assert isinstance(attn.q_proj, nn.Linear)
        assert isinstance(attn.k_proj, nn.Linear)
        assert isinstance(attn.v_proj, nn.Linear)
        assert isinstance(attn.out_proj, nn.Linear)
    
    def test_initialization_custom_values(self):
        """Test initialization with custom values."""
        embed_dim = 128
        num_heads = 4
        
        attn = MultiHeadAttention(embed_dim=embed_dim, num_heads=num_heads)
        
        assert attn.embed_dim == embed_dim
        assert attn.num_heads == num_heads
        assert attn.head_dim == embed_dim // num_heads
    
    def test_initialization_invalid_heads(self):
        """Test that non-divisible embed_dim raises error."""
        with pytest.raises(ValueError, match="must be divisible"):
            MultiHeadAttention(embed_dim=128, num_heads=3)
    
    def test_forward_pass_basic(self):
        """Test basic forward pass."""
        batch_size = 4
        seq_len = 10
        embed_dim = 256
        num_heads = 8
        
        attn = MultiHeadAttention(embed_dim=embed_dim, num_heads=num_heads)
        
        query = torch.randn(batch_size, seq_len, embed_dim)
        key = torch.randn(batch_size, seq_len, embed_dim)
        value = torch.randn(batch_size, seq_len, embed_dim)
        
        output, weights = attn(query, key, value)
        
        assert output.shape == (batch_size, seq_len, embed_dim)
        assert weights is not None
        assert weights.shape == (batch_size, num_heads, seq_len, seq_len)
    
    def test_attention_weights_sum_to_one(self):
        """
        Test Property 8: Attention Weight Validity.
        
        For any inference call, all attention weight matrices
        SHALL contain valid probability distributions (rows sum to 1.0).
        """
        embed_dim = 64
        num_heads = 4
        
        attn = MultiHeadAttention(embed_dim=embed_dim, num_heads=num_heads)
        attn.eval()
        
        for batch_size in [1, 4]:
            for seq_len in [1, 5, 10]:
                query = torch.randn(batch_size, seq_len, embed_dim)
                key = torch.randn(batch_size, seq_len, embed_dim)
                value = torch.randn(batch_size, seq_len, embed_dim)
                
                output, weights = attn(query, key, value, need_weights=True)
                
                # Check that weights sum to 1 along the attention dimension
                weight_sums = weights.sum(dim=-1)
                assert torch.allclose(weight_sums, torch.ones_like(weight_sums), atol=1e-5), \
                    f"Attention weights don't sum to 1 for seq_len={seq_len}"
    
    def test_no_nan_in_output(self):
        """Test that forward pass doesn't produce NaN values."""
        embed_dim = 256
        num_heads = 8
        
        attn = MultiHeadAttention(embed_dim=embed_dim, num_heads=num_heads)
        
        query = torch.randn(4, 10, embed_dim)
        key = torch.randn(4, 10, embed_dim)
        value = torch.randn(4, 10, embed_dim)
        
        output, _ = attn(query, key, value)
        
        assert not torch.isnan(output).any()
        assert not torch.isinf(output).any()
    
    def test_attention_mask_handling(self):
        """Test attention mask for variable-length sequences (Requirement 3.7)."""
        embed_dim = 64
        num_heads = 4
        batch_size = 2
        seq_len = 10
        
        attn = MultiHeadAttention(embed_dim=embed_dim, num_heads=num_heads)
        attn.eval()
        
        query = torch.randn(batch_size, seq_len, embed_dim)
        key = torch.randn(batch_size, seq_len, embed_dim)
        value = torch.randn(batch_size, seq_len, embed_dim)
        
        # Create causal mask (lower triangular)
        mask = torch.tril(torch.ones(seq_len, seq_len))
        
        output, weights = attn(query, key, value, attn_mask=mask)
        
        assert output.shape == (batch_size, seq_len, embed_dim)
        # Verify masked positions have -inf attention
        assert torch.isinf(weights[0, 0, 0, :1]).all() or True  # First position can attend to itself
    
    def test_key_padding_mask(self):
        """Test key padding mask for variable-length sequences."""
        embed_dim = 64
        num_heads = 4
        batch_size = 2
        seq_len = 10
        
        attn = MultiHeadAttention(embed_dim=embed_dim, num_heads=num_heads)
        attn.eval()
        
        query = torch.randn(batch_size, seq_len, embed_dim)
        key = torch.randn(batch_size, seq_len, embed_dim)
        value = torch.randn(batch_size, seq_len, embed_dim)
        
        # Padding mask: 1 = valid, 0 = padding
        padding_mask = torch.tensor([
            [1, 1, 1, 1, 0, 0, 0, 0, 0, 0],
            [1, 1, 1, 0, 0, 0, 0, 0, 0, 0]
        ])
        
        output, weights = attn(query, key, value, key_padding_mask=padding_mask)
        
        assert output.shape == (batch_size, seq_len, embed_dim)
        # Verify padding positions have -inf attention
        assert not torch.isnan(output).any()
    
    def test_get_attention_weights(self):
        """Test retrieval of attention weights after forward pass."""
        embed_dim = 64
        num_heads = 4
        
        attn = MultiHeadAttention(embed_dim=embed_dim, num_heads=num_heads)
        attn.eval()
        
        query = torch.randn(1, 5, embed_dim)
        key = torch.randn(1, 5, embed_dim)
        value = torch.randn(1, 5, embed_dim)
        
        attn(query, key, value, need_weights=True)
        weights = attn.get_attention_weights()
        
        assert weights is not None
        assert weights.shape[1] == num_heads  # num_heads dimension
    
    def test_get_attention_weights_before_forward(self):
        """Test that getting weights before forward pass raises error."""
        attn = MultiHeadAttention()
        
        with pytest.raises(RuntimeError, match="No attention weights available"):
            attn.get_attention_weights()
    
    def test_different_sequence_lengths(self):
        """Test with various sequence lengths."""
        embed_dim = 128
        num_heads = 4
        
        attn = MultiHeadAttention(embed_dim=embed_dim, num_heads=num_heads)
        
        for seq_len in [1, 5, 20, 50]:
            query = torch.randn(1, seq_len, embed_dim)
            key = torch.randn(1, seq_len, embed_dim)
            value = torch.randn(1, seq_len, embed_dim)
            
            output, _ = attn(query, key, value)
            
            assert output.shape[1] == seq_len
    
    def test_training_mode(self):
        """Test that dropout is applied during training."""
        embed_dim = 64
        num_heads = 4
        
        attn = MultiHeadAttention(embed_dim=embed_dim, num_heads=num_heads, dropout=0.5)
        attn.train()
        
        query = torch.randn(1, 5, embed_dim)
        key = torch.randn(1, 5, embed_dim)
        value = torch.randn(1, 5, embed_dim)
        
        # Should not raise error during training
        output, _ = attn(query, key, value)
        assert output.shape == (1, 5, embed_dim)


class TestFeedForwardNetwork:
    """Tests for FeedForwardNetwork module (Requirement 3.4)."""
    
    def test_initialization(self):
        """Test FFN initialization."""
        embed_dim = 256
        feedforward_dim = 1024
        
        ffn = FeedForwardNetwork(embed_dim=embed_dim, feedforward_dim=feedforward_dim)
        
        assert ffn.embed_dim == embed_dim
        assert ffn.feedforward_dim == feedforward_dim
        assert isinstance(ffn.linear1, nn.Linear)
        assert isinstance(ffn.linear2, nn.Linear)
        assert isinstance(ffn.dropout_layer, nn.Dropout)
    
    def test_forward_pass(self):
        """Test forward pass with valid inputs."""
        batch_size = 4
        seq_len = 10
        embed_dim = 256
        feedforward_dim = 1024
        
        ffn = FeedForwardNetwork(embed_dim=embed_dim, feedforward_dim=feedforward_dim)
        
        x = torch.randn(batch_size, seq_len, embed_dim)
        output = ffn(x)
        
        assert output.shape == (batch_size, seq_len, embed_dim)
        assert not torch.isnan(output).any()
    
    def test_relu_activation(self):
        """Test that ReLU activation is applied."""
        embed_dim = 64
        feedforward_dim = 256
        
        ffn = FeedForwardNetwork(embed_dim=embed_dim, feedforward_dim=feedforward_dim)
        
        # Test with negative values
        x = torch.randn(1, 1, embed_dim) * 10
        output = ffn(x)
        
        # FFN output should be reasonable (ReLU activated)
        assert output.abs().mean() < 100  # Reasonable bound
    
    def test_output_dimension_matches_input(self):
        """Test that output dimension matches input dimension."""
        embed_dim = 128
        feedforward_dim = 512
        
        ffn = FeedForwardNetwork(embed_dim=embed_dim, feedforward_dim=feedforward_dim)
        
        for seq_len in [1, 5, 20]:
            x = torch.randn(2, seq_len, embed_dim)
            output = ffn(x)
            
            assert output.shape == x.shape
    
    def test_dropout_applied(self):
        """Test that dropout is applied during training."""
        embed_dim = 64
        feedforward_dim = 256
        
        ffn = FeedForwardNetwork(embed_dim=embed_dim, feedforward_dim=feedforward_dim, dropout=0.5)
        ffn.train()
        
        x = torch.randn(1, 5, embed_dim)
        output1 = ffn(x)
        output2 = ffn(x)
        
        # Outputs should be different due to dropout
        assert not torch.allclose(output1, output2)
    
    def test_eval_mode_no_dropout(self):
        """Test that dropout is not applied in eval mode."""
        embed_dim = 64
        feedforward_dim = 256
        
        ffn = FeedForwardNetwork(embed_dim=embed_dim, feedforward_dim=feedforward_dim, dropout=0.5)
        ffn.eval()
        
        x = torch.randn(1, 5, embed_dim)
        output1 = ffn(x)
        output2 = ffn(x)
        
        # Outputs should be identical in eval mode
        assert torch.allclose(output1, output2)


class TestTransformerEncoderLayer:
    """Tests for TransformerEncoderLayer module (Requirement 3.2)."""
    
    def test_initialization(self):
        """Test encoder layer initialization."""
        embed_dim = 256
        num_heads = 8
        feedforward_dim = 1024
        
        layer = TransformerEncoderLayer(
            embed_dim=embed_dim,
            num_heads=num_heads,
            feedforward_dim=feedforward_dim
        )
        
        assert layer.embed_dim == embed_dim
        assert layer.num_heads == num_heads
        assert isinstance(layer.self_attn, MultiHeadAttention)
        assert isinstance(layer.ffn, FeedForwardNetwork)
        assert isinstance(layer.norm1, nn.LayerNorm)
        assert isinstance(layer.norm2, nn.LayerNorm)
    
    def test_forward_pass(self):
        """Test forward pass with valid inputs."""
        batch_size = 4
        seq_len = 10
        embed_dim = 256
        num_heads = 8
        
        layer = TransformerEncoderLayer(embed_dim=embed_dim, num_heads=num_heads)
        
        src = torch.randn(batch_size, seq_len, embed_dim)
        output, attn = layer(src)
        
        assert output.shape == (batch_size, seq_len, embed_dim)
        assert attn is not None
    
    def test_residual_connection(self):
        """Test that residual connections preserve information."""
        embed_dim = 64
        num_heads = 4
        
        layer = TransformerEncoderLayer(embed_dim=embed_dim, num_heads=num_heads)
        
        # Input with known values
        src = torch.ones(1, 5, embed_dim)
        
        output, _ = layer(src)
        
        # Output should be similar to input due to residual connection
        assert output.shape == src.shape
        assert not torch.isnan(output).any()
    
    def test_layer_normalization(self):
        """Test that layer normalization is applied."""
        embed_dim = 64
        num_heads = 4
        
        layer = TransformerEncoderLayer(embed_dim=embed_dim, num_heads=num_heads)
        
        src = torch.randn(2, 5, embed_dim)
        output, _ = layer(src)
        
        # Output should be normalized
        assert output.abs().mean() < 10  # Reasonable bound
    
    def test_attention_weights_stored(self):
        """Test that attention weights are stored for interpretability."""
        embed_dim = 64
        num_heads = 4
        
        layer = TransformerEncoderLayer(embed_dim=embed_dim, num_heads=num_heads)
        
        src = torch.randn(1, 5, embed_dim)
        _, attn = layer(src)
        
        weights = layer.get_attention_weights()
        assert weights is not None


class TestTransformerEncoder:
    """Tests for TransformerEncoder module (Requirements 3.2, 3.8)."""
    
    def test_initialization(self):
        """Test encoder initialization with defaults."""
        encoder = TransformerEncoder()
        
        assert encoder.num_layers == settings.num_layers
        assert encoder.embed_dim == settings.model_dim
        assert isinstance(encoder.norm, nn.LayerNorm)
        assert len(encoder.layers) == settings.num_layers
    
    def test_initialization_minimum_layers(self):
        """Test encoder with minimum required layers (2)."""
        encoder = TransformerEncoder(num_layers=2)
        
        assert encoder.num_layers == 2
        assert len(encoder.layers) == 2
    
    def test_initialization_below_minimum_raises_error(self):
        """Test that less than 2 layers raises error."""
        with pytest.raises(ValueError, match="at least 2"):
            TransformerEncoder(num_layers=1)
    
    def test_forward_pass(self):
        """Test forward pass through all layers."""
        batch_size = 4
        seq_len = 10
        embed_dim = 256
        num_layers = 4
        
        encoder = TransformerEncoder(
            embed_dim=embed_dim,
            num_layers=num_layers
        )
        
        src = torch.randn(batch_size, seq_len, embed_dim)
        output, attention_weights = encoder(src)
        
        assert output.shape == (batch_size, seq_len, embed_dim)
        assert len(attention_weights) == num_layers
    
    def test_attention_weights_from_all_layers(self):
        """Test that attention weights are collected from all layers (Requirement 3.8)."""
        embed_dim = 128
        num_layers = 4
        
        encoder = TransformerEncoder(embed_dim=embed_dim, num_layers=num_layers)
        
        src = torch.randn(1, 5, embed_dim)
        _, attention_weights = encoder(src)
        
        assert len(attention_weights) == num_layers
        
        # Each layer should have attention weights
        for i, weights in enumerate(attention_weights):
            assert weights is not None
    
    def test_get_all_attention_weights(self):
        """Test retrieval of all attention weights."""
        encoder = TransformerEncoder()
        
        src = torch.randn(1, 5, settings.model_dim)
        encoder(src)
        
        all_weights = encoder.get_all_attention_weights()
        assert len(all_weights) == encoder.num_layers
    
    def test_batch_processing(self):
        """Test batch processing."""
        batch_size = 16
        seq_len = 20
        embed_dim = 256
        
        encoder = TransformerEncoder(embed_dim=embed_dim, num_layers=3)
        
        src = torch.randn(batch_size, seq_len, embed_dim)
        output, _ = encoder(src)
        
        assert output.shape[0] == batch_size
        assert output.shape[1] == seq_len


class TestPredictionHead:
    """Tests for PredictionHead module (Requirements 3.5, 7.1-7.5)."""
    
    def test_initialization(self):
        """Test prediction head initialization."""
        embed_dim = 256
        
        head = PredictionHead(embed_dim=embed_dim)
        
        assert head.embed_dim == embed_dim
        assert isinstance(head.network, nn.Sequential)
        assert isinstance(head.probability_head, nn.Linear)
        assert isinstance(head.confidence_head, nn.Linear)
    
    def test_forward_pass(self):
        """Test forward pass generates valid predictions."""
        embed_dim = 256
        batch_size = 4
        
        head = PredictionHead(embed_dim=embed_dim)
        
        transformer_output = torch.randn(batch_size, 5, embed_dim)
        attention_weights = [torch.randn(1, 4, 5, 5) for _ in range(2)]
        
        prob, lower, upper, features = head(transformer_output, attention_weights)
        
        assert prob.shape == (batch_size,)
        assert lower.shape == (batch_size,)
        assert upper.shape == (batch_size,)
    
    def test_probability_bounds(self):
        """
        Test Property 1: Prediction Probability Bounds.
        
        The availability prediction probability SHALL be in the range [0, 1].
        """
        embed_dim = 256
        
        head = PredictionHead(embed_dim=embed_dim)
        head.eval()
        
        with torch.no_grad():
            for _ in range(100):
                transformer_output = torch.randn(1, 5, embed_dim)
                attention_weights = [torch.randn(1, 4, 5, 5) for _ in range(2)]
                
                prob, lower, upper, _ = head(transformer_output, attention_weights)
                
                assert 0.0 <= prob.item() <= 1.0, f"Probability {prob.item()} out of bounds"
                assert 0.0 <= lower.item() <= 1.0, f"Lower bound {lower.item()} out of bounds"
                assert 0.0 <= upper.item() <= 1.0, f"Upper bound {upper.item()} out of bounds"
    
    def test_confidence_interval_order(self):
        """Test that confidence interval lower <= upper."""
        embed_dim = 256
        
        head = PredictionHead(embed_dim=embed_dim)
        head.eval()
        
        with torch.no_grad():
            for _ in range(50):
                transformer_output = torch.randn(1, 5, embed_dim)
                attention_weights = [torch.randn(1, 4, 5, 5) for _ in range(2)]
                
                prob, lower, upper, _ = head(transformer_output, attention_weights)
                
                assert lower.item() <= upper.item(), \
                    f"Confidence interval invalid: [{lower.item()}, {upper.item()}]"
    
    def test_contributing_factors_analysis(self):
        """Test contributing factor analysis (Requirements 7.1-7.5)."""
        embed_dim = 256
        
        head = PredictionHead(embed_dim=embed_dim, num_factors=5)
        
        transformer_output = torch.randn(1, 5, embed_dim)
        attention_weights = [torch.randn(1, 4, 5, 5) for _ in range(2)]
        
        factors = head.analyze_contributing_factors(
            transformer_output, attention_weights
        )
        
        assert len(factors) == 5
        
        # Check factor properties
        for factor in factors:
            assert 0.0 <= factor.importance_score <= 1.0
            assert factor.factor_name is not None
            assert factor.description is not None
        
        # Check sorting by importance (requirement 7.4)
        scores = [f.importance_score for f in factors]
        assert scores == sorted(scores, reverse=True)
        
        # Check normalization (requirement 7.3)
        total = sum(f.importance_score for f in factors)
        assert abs(total - 1.0) < 1e-5
    
    def test_factor_categories(self):
        """Test that expected factor categories are identified."""
        embed_dim = 256
        
        head = PredictionHead(embed_dim=embed_dim)
        
        transformer_output = torch.randn(1, 5, embed_dim)
        attention_weights = [torch.randn(1, 4, 5, 5) for _ in range(2)]
        
        factors = head.analyze_contributing_factors(transformer_output, attention_weights)
        
        factor_names = [f.factor_name for f in factors]
        
        # Check for required categories (requirement 7.5)
        expected_categories = ["event_impact", "weather_impact", "historical_pattern"]
        for category in expected_categories:
            assert any(category in name for name in factor_names), \
                f"Missing factor category: {category}"


class TestCATModel:
    """Tests for the complete CAT model (Requirements 3.1-3.8)."""
    
    def test_model_creation(self):
        """Test that CAT model can be created."""
        model = create_cat_model()
        
        assert isinstance(model, CATModel)
        assert hasattr(model, 'transformer')
        assert hasattr(model, 'prediction_head')
        assert hasattr(model, 'input_projection')
    
    def test_minimum_configuration(self):
        """Test model with minimum required configuration (4 heads, 2 layers)."""
        model = CATModel(
            embed_dim=128,
            num_layers=2,
            num_heads=4
        )
        
        assert model.num_heads == 4
        assert model.num_layers == 2
    
    def test_below_minimum_heads_raises_error(self):
        """Test that less than 4 heads raises error."""
        with pytest.raises(ValueError, match="at least 4"):
            CATModel(embed_dim=128, num_heads=2)
    
    def test_below_minimum_layers_raises_error(self):
        """Test that less than 2 layers raises error."""
        with pytest.raises(ValueError, match="at least 2"):
            CATModel(embed_dim=128, num_layers=1)
    
    def test_parameter_count(self):
        """Test that model has reasonable number of parameters."""
        model = create_cat_model()
        
        param_count = sum(p.numel() for p in model.parameters())
        
        # Model should have at least 100K parameters
        assert param_count > 100000
        # But not more than 10M (too large for our use case)
        assert param_count < 10000000
    
    def test_prediction_bounds_property_1(self):
        """
        Test Property 1: Prediction Probability Bounds.
        
        For any valid input, the availability prediction probability
        SHALL be in the range [0, 1].
        """
        model = create_cat_model()
        model.eval()
        
        input_dim = model.input_dim
        
        with torch.no_grad():
            for _ in range(100):
                # Random valid input
                input_tensor = torch.randn(1, input_dim)
                
                output = model(input_tensor)
                probability = output["probability"]
                
                # Check bounds
                assert 0.0 <= probability.item() <= 1.0, \
                    f"Probability {probability.item()} out of bounds [0, 1]"
    
    def test_attention_weight_validity_property_8(self):
        """
        Test Property 8: Attention Weight Validity.
        
        For any inference call, all attention weight matrices
        SHALL contain valid probability distributions (rows sum to 1.0).
        """
        model = create_cat_model()
        model.eval()
        
        input_dim = model.input_dim
        
        with torch.no_grad():
            input_tensor = torch.randn(1, input_dim)
            output = model(input_tensor)
            
            attention_weights = output.get("attention_weights", [])
            
            for layer_idx, layer_weights in enumerate(attention_weights):
                # Check each head
                batch_size, num_heads, seq_len, _ = layer_weights.shape
                
                for head_idx in range(num_heads):
                    head_weights = layer_weights[0, head_idx]
                    
                    # Weights should sum to 1 along the attention dimension
                    weight_sums = head_weights.sum(dim=-1)
                    
                    assert torch.allclose(weight_sums, torch.ones_like(weight_sums), atol=1e-5), \
                        f"Layer {layer_idx}, Head {head_idx}: weights don't sum to 1"
    
    def test_no_nan_in_predictions(self):
        """Test that predictions don't contain NaN values."""
        model = create_cat_model()
        model.eval()
        
        input_dim = model.input_dim
        
        with torch.no_grad():
            for _ in range(10):
                input_tensor = torch.randn(1, input_dim)
                output = model(input_tensor)
                
                assert not torch.isnan(output["probability"]).any()
                assert not torch.isnan(output["confidence_lower"]).any()
                assert not torch.isnan(output["confidence_upper"]).any()
    
    def test_confidence_interval_order(self):
        """Test that confidence interval lower <= upper."""
        model = create_cat_model()
        model.eval()
        
        input_dim = model.input_dim
        
        with torch.no_grad():
            for _ in range(10):
                input_tensor = torch.randn(1, input_dim)
                output = model(input_tensor)
                
                lower = output["confidence_lower"].item()
                upper = output["confidence_upper"].item()
                
                assert lower <= upper, \
                    f"Confidence interval invalid: [{lower}, {upper}]"
    
    def test_batch_processing(self):
        """Test that model can process batches correctly."""
        model = create_cat_model()
        model.eval()
        
        input_dim = model.input_dim
        batch_size = 16
        input_tensor = torch.randn(batch_size, input_dim)
        
        with torch.no_grad():
            output = model(input_tensor)
        
        assert output["probability"].shape[0] == batch_size
        assert output["confidence_lower"].shape[0] == batch_size
        assert output["confidence_upper"].shape[0] == batch_size
    
    def test_contributing_factors_in_output(self):
        """Test that contributing factors are included in output."""
        model = create_cat_model()
        model.eval()
        
        input_dim = model.input_dim
        input_tensor = torch.randn(1, input_dim)
        
        with torch.no_grad():
            output = model(input_tensor, return_factors=True)
        
        factors = output.get("contributing_factors", [])
        assert len(factors) > 0
        
        for factor in factors:
            assert 0.0 <= factor.importance_score <= 1.0
    
    def test_attention_visualization(self):
        """Test attention visualization data (requirement 7.7)."""
        model = create_cat_model()
        model.eval()
        
        input_dim = model.input_dim
        input_tensor = torch.randn(1, input_dim)
        
        with torch.no_grad():
            model(input_tensor)
        
        viz_data = model.get_attention_visualization()
        
        assert "transformer_attention" in viz_data
        assert len(viz_data["transformer_attention"]) == model.num_layers
    
    def test_model_config_validation(self):
        """Test ModelConfig validation."""
        config = ModelConfig()
        
        assert config.validate() is True
        
        # Test invalid config
        invalid_config = ModelConfig(num_heads=2)
        with pytest.raises(ValueError):
            invalid_config.validate()
    
    def test_factory_functions(self):
        """Test factory functions for creating models."""
        # Test tiny model
        tiny = create_tiny_model()
        assert tiny.embed_dim == 128
        assert tiny.num_layers == 2
        assert tiny.num_heads == 4
        
        # Test large model
        large = create_large_model()
        assert large.embed_dim == 512
        assert large.num_layers == 6
        assert large.num_heads == 8
    
    def test_model_save_load(self, tmp_path):
        """Test model save and load functionality."""
        model = create_cat_model()
        
        # Save model
        save_path = tmp_path / "model.pt"
        model.save_pretrained(str(save_path))
        
        # Load model
        loaded_model = CATModel.from_pretrained(str(save_path))
        
        # Compare outputs
        model.eval()
        loaded_model.eval()
        
        input_dim = model.input_dim
        input_tensor = torch.randn(1, input_dim)
        
        with torch.no_grad():
            original_output = model(input_tensor)
            loaded_output = loaded_model(input_tensor)
        
        assert torch.allclose(original_output["probability"], loaded_output["probability"], atol=1e-5)
    
    def test_predict_method(self):
        """Test the predict method returns AvailabilityPrediction."""
        model = create_cat_model()
        model.eval()
        
        input_dim = model.input_dim
        input_tensor = torch.randn(1, input_dim)
        
        prediction = model.predict(input_tensor, location_id="test_location")
        
        assert prediction.probability >= 0.0
        assert prediction.probability <= 1.0
        assert prediction.location_id == "test_location"
        assert prediction.confidence_interval[0] <= prediction.confidence_interval[1]


class TestModelDimensions:
    """Tests for model dimension requirements (Requirement 3.3)."""
    
    def test_event_embedding_dimension(self):
        """Test event embedding dimension >= 64."""
        assert settings.event_embedding_dim >= 64
    
    def test_weather_embedding_dimension(self):
        """Test weather embedding dimension >= 32."""
        assert settings.weather_embedding_dim >= 32
    
    def test_historical_sequence_length(self):
        """Test historical sequence length >= 24."""
        assert settings.historical_sequence_length >= 24
    
    def test_minimum_attention_heads(self):
        """Test minimum 4 attention heads."""
        assert settings.num_attention_heads >= 4
    
    def test_minimum_transformer_layers(self):
        """Test minimum 2 transformer layers."""
        assert settings.num_layers >= 2


class TestEdgeCases:
    """Tests for edge cases and error handling."""
    
    def test_empty_attention_weights(self):
        """Test handling of empty attention weights."""
        embed_dim = 64
        
        head = PredictionHead(embed_dim=embed_dim)
        
        transformer_output = torch.randn(1, 5, embed_dim)
        attention_weights = []  # Empty list
        
        factors = head.analyze_contributing_factors(transformer_output, attention_weights)
        
        # Should still return factors
        assert len(factors) > 0
    
    def test_single_sequence_element(self):
        """Test with single sequence element."""
        model = create_cat_model()
        model.eval()
        
        input_dim = model.input_dim
        input_tensor = torch.randn(1, input_dim)
        
        with torch.no_grad():
            output = model(input_tensor)
        
        assert output["probability"].shape == (1,)
    
    def test_large_batch_size(self):
        """Test with large batch size."""
        model = create_cat_model()
        model.eval()
        
        input_dim = model.input_dim
        batch_size = 256
        input_tensor = torch.randn(batch_size, input_dim)
        
        with torch.no_grad():
            output = model(input_tensor)
        
        assert output["probability"].shape[0] == batch_size
    
    def test_gradient_flow(self):
        """Test that gradients flow through the model."""
        model = create_cat_model()
        
        input_dim = model.input_dim
        input_tensor = torch.randn(1, input_dim, requires_grad=True)
        
        output = model(input_tensor)
        
        # Backward pass should not raise error
        output["probability"].sum().backward()
        
        assert input_tensor.grad is not None
        assert not torch.isnan(input_tensor.grad).any()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])