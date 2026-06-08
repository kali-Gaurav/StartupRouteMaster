"""
Transformer Model Architecture for the Contextual Availability Transformer (CAT) system.
Implements multi-head self-attention, feed-forward networks, and prediction heads.

This module re-exports the complete model architecture from modular components.
The actual implementations are in:
- attention.py: Multi-head attention mechanism
- feed_forward.py: Feed-forward network layer
- encoder.py: Transformer encoder layer and stack
- prediction_head.py: Prediction head and confidence estimation
"""

# Re-export all components for backward compatibility
from .attention import MultiHeadAttention
from .feed_forward import FeedForwardNetwork
from .encoder import TransformerEncoderLayer, TransformerEncoder
from .prediction_head import PredictionHead, ConfidenceIntervalEstimator

# Import CATModel and factory functions directly (not from .transformer to avoid circular import)
import math
from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor

from ..config import settings
from ..models.schemas import (
    AvailabilityPrediction, ContributingFactor, RailwayAvailabilityPrediction, TrainClass
)


class CATModel(nn.Module):
    """
    Complete Contextual Availability Transformer model.
    
    Combines:
    - Input projection (concatenation of contextual embeddings)
    - Transformer encoder stack with configurable layers
    - Prediction head with confidence intervals
    - Contributing factor analysis from attention weights
    
    Architecture follows requirements:
    - Multi-head self-attention with at least 4 attention heads (3.1)
    - At least 2 transformer layers with residual connections and layer norm (3.2)
    - Event embeddings >= 64, weather embeddings >= 32, history >= 24 (3.3)
    - Feed-forward network with at least one hidden layer (3.4)
    - Sigmoid activation for final prediction (3.5)
    - Attention weights for all heads for interpretability (3.6, 3.7, 3.8)
    """
    
    def __init__(
        self,
        input_dim: int = None,
        embed_dim: int = None,
        num_layers: int = None,
        num_heads: int = None,
        feedforward_dim: int = None,
        dropout: float = None,
        num_factors: int = 5
    ):
        """
        Initialize the CAT model.
        
        Args:
            input_dim: Total input dimension (calculated if None)
            embed_dim: Transformer embedding dimension
            num_layers: Number of transformer layers (minimum 2)
            num_heads: Number of attention heads (minimum 4)
            feedforward_dim: Feed-forward hidden dimension
            dropout: Dropout probability
            num_factors: Number of contributing factors to identify
        """
        super().__init__()
        
        # Core dimensions
        self.embed_dim = embed_dim or settings.model_dim
        self.num_layers = num_layers or settings.num_layers
        self.num_heads = num_heads or settings.num_attention_heads
        self.feedforward_dim = feedforward_dim or settings.feedforward_dim
        self.dropout = dropout or settings.dropout_rate
        self.num_factors = num_factors
        
        # Validate minimum requirements
        if self.num_heads < 4:
            raise ValueError(f"num_heads ({self.num_heads}) must be at least 4 per requirements")
        if self.num_layers < 2:
            raise ValueError(f"num_layers ({self.num_layers}) must be at least 2 per requirements")
        
        # Calculate input dimension if not provided
        if input_dim is None:
            self.input_dim = (
                settings.event_embedding_dim +
                settings.weather_embedding_dim +
                settings.historical_sequence_length * settings.event_embedding_dim +
                settings.temporal_encoding_dim
            )
        else:
            self.input_dim = input_dim
        
        # Input projection layer
        self.input_projection = nn.Linear(self.input_dim, self.embed_dim)
        
        # Transformer encoder stack (requirement 3.2)
        self.transformer = TransformerEncoder(
            embed_dim=self.embed_dim,
            num_layers=self.num_layers,
            num_heads=self.num_heads,
            feedforward_dim=self.feedforward_dim,
            dropout=self.dropout
        )
        
        # Prediction head (requirement 3.5)
        self.prediction_head = PredictionHead(
            embed_dim=self.embed_dim,
            hidden_dim=self.feedforward_dim,
            num_factors=self.num_factors
        )
        
        # Confidence interval estimator (requirement 2.3, 2.4)
        self.confidence_estimator = ConfidenceIntervalEstimator(
            embed_dim=self.embed_dim,
            hidden_dim=self.feedforward_dim // 4
        )
        
        # Initialize weights
        self._init_weights()
    
    def _init_weights(self):
        """Initialize model weights using appropriate strategies."""
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)
            elif isinstance(module, nn.LayerNorm):
                nn.init.ones_(module.weight)
                nn.init.zeros_(module.bias)
            elif isinstance(module, nn.Embedding):
                nn.init.normal_(module.weight, mean=0, std=0.02)
    
    def forward(
        self,
        input_tensor: Tensor,
        return_factors: bool = True
    ) -> Dict[str, Tensor]:
        """
        Forward pass through the CAT model.
        
        Args:
            input_tensor: Concatenated input features [batch_size, input_dim]
            return_factors: Whether to return contributing factors
            
        Returns:
            Dictionary containing:
                - probability: Availability probability [batch_size]
                - confidence_lower: Lower confidence bound [batch_size]
                - confidence_upper: Upper confidence bound [batch_size]
                - attention_weights: List of attention tensors
                - contributing_factors: List of ContributingFactor (if return_factors)
        """
        batch_size = input_tensor.size(0)
        
        # Project input to embed dimension
        projected = self.input_projection(input_tensor)
        
        # Add sequence dimension if needed for transformer
        if projected.dim() == 2:
            projected = projected.unsqueeze(1)  # [batch_size, 1, embed_dim]
        
        # Apply transformer encoder
        transformer_output, attention_weights = self.transformer(projected)
        
        # Generate predictions
        probability, confidence_lower, confidence_upper, features = self.prediction_head(
            transformer_output, attention_weights
        )
        
        # Prepare output
        output = {
            "probability": probability,
            "confidence_lower": confidence_lower,
            "confidence_upper": confidence_upper,
            "attention_weights": attention_weights
        }
        
        # Analyze contributing factors (requirements 7.1-7.5)
        if return_factors:
            factors = self.prediction_head.analyze_contributing_factors(
                transformer_output, attention_weights
            )
            output["contributing_factors"] = factors
        
        return output
    
    def predict(
        self,
        input_tensor: Tensor,
        location_id: Optional[str] = None,
        prediction_time: Optional[str] = None,
        model_version: Optional[str] = None
    ) -> AvailabilityPrediction:
        """
        Generate a complete availability prediction.
        
        Args:
            input_tensor: Concatenated input features [batch_size, input_dim]
            location_id: Optional location identifier
            prediction_time: Optional prediction timestamp
            model_version: Optional model version string
            
        Returns:
            AvailabilityPrediction object with probability, confidence, and factors
        """
        from datetime import datetime
        
        model_version = model_version or settings.model_version
        
        # Forward pass
        self.eval()
        with torch.no_grad():
            output = self.forward(input_tensor, return_factors=True)
        
        # Extract values
        probability = output["probability"].item()
        confidence_lower = output["confidence_lower"].item()
        confidence_upper = output["confidence_upper"].item()
        factors = output.get("contributing_factors", [])
        
        # Parse prediction time
        if prediction_time is None:
            pred_time = datetime.utcnow()
        elif isinstance(prediction_time, str):
            pred_time = datetime.fromisoformat(prediction_time.replace('Z', '+00:00'))
        else:
            pred_time = prediction_time
        
        return AvailabilityPrediction(
            probability=probability,
            confidence_interval=(confidence_lower, confidence_upper),
            contributing_factors=factors,
            location_id=location_id or "unknown",
            prediction_time=pred_time,
            model_version=model_version
        )
    
    def predict_railway(
        self,
        context_tensor: Tensor,
        railway_tensor: Optional[Tensor] = None,
        train_id: Optional[str] = None,
        route_id: Optional[str] = None,
        departure_time: Optional[str] = None,
        model_version: Optional[str] = None
    ) -> RailwayAvailabilityPrediction:
        """
        Generate a complete railway availability prediction with class-level granularity.
        
        Args:
            context_tensor: Context features [batch_size, input_dim]
            railway_tensor: Optional railway-specific features
            train_id: Optional train identifier
            route_id: Optional route identifier
            departure_time: Optional departure time
            model_version: Optional model version string
            
        Returns:
            RailwayAvailabilityPrediction with class probabilities and fares
        """
        from datetime import datetime
        
        model_version = model_version or settings.model_version
        
        # Forward pass
        self.eval()
        with torch.no_grad():
            output = self.forward(context_tensor, return_factors=True)
        
        # Get class probabilities (using single class for now)
        class_probs = output["probability"]
        confidence_lower = output["confidence_lower"]
        confidence_upper = output["confidence_upper"]
        factors = output.get("contributing_factors", [])
        
        # Map to train classes
        classes = list(TrainClass)
        class_probabilities = {
            classes[i]: class_probs[i].item() if i < len(class_probs) else 0.0
            for i in range(min(len(classes), self.prediction_head.num_classes))
        }
        
        # Generate dynamic fares (placeholder - would use fare prediction model)
        dynamic_fares = {
            classes[i]: 100.0 + i * 50.0  # Placeholder values
            for i in range(len(classes))
        }
        
        # Parse departure time
        if departure_time is None:
            dep_time = datetime.utcnow()
        elif isinstance(departure_time, str):
            dep_time = datetime.fromisoformat(departure_time.replace('Z', '+00:00'))
        else:
            dep_time = departure_time
        
        # Calculate overall confidence
        overall_confidence = 1.0 - (confidence_upper - confidence_lower).clamp(0, 1).item()
        
        return RailwayAvailabilityPrediction(
            train_id=train_id or "unknown",
            route_id=route_id or "unknown",
            departure_time=dep_time,
            class_availability=class_probabilities,
            predicted_fares=dynamic_fares,
            overall_confidence=overall_confidence,
            factors=factors,
            model_version=model_version
        )
    
    def get_attention_visualization(self) -> Dict[str, List[Tensor]]:
        """Get attention weights for visualization (requirement 7.7)."""
        return {
            "transformer_attention": self.transformer.get_all_attention_weights()
        }
    
    def validate_attention_weights(self) -> bool:
        """
        Validate that attention weights form valid probability distributions.
        
        Property 8: Attention Weight Validity.
        
        Returns:
            True if all attention weights are valid
        """
        self.eval()
        with torch.no_grad():
            # Create dummy input
            input_tensor = torch.randn(1, self.input_dim)
            output = self.forward(input_tensor, return_factors=True)
            
            attention_weights = output.get("attention_weights", [])
            
            for layer_weights in attention_weights:
                # Check each head in each layer
                for head_idx in range(layer_weights.size(1)):
                    head_weights = layer_weights[0, head_idx]  # [seq_len, seq_len]
                    
                    # Weights should sum to 1 along the attention dimension
                    weight_sums = head_weights.sum(dim=-1)
                    
                    if not torch.allclose(weight_sums, torch.ones_like(weight_sums), atol=1e-5):
                        return False
            
            return True
    
    @classmethod
    def from_pretrained(cls, path: str, map_location: str = "cpu") -> 'CATModel':
        """Load a pretrained model from disk."""
        device = torch.device(map_location if torch.cuda.is_available() else "cpu")
        state_dict = torch.load(path, map_location=device)
        model = cls()
        model.load_state_dict(state_dict)
        model.eval()
        return model
    
    def save_pretrained(self, path: str) -> None:
        """Save model weights to disk."""
        torch.save(self.state_dict(), path)


@dataclass
class ModelConfig:
    """
    Configuration for the CAT model.
    
    Provides a structured way to configure model dimensions and layer counts
    (requirement 3.8).
    """
    input_dim: Optional[int] = None
    embed_dim: int = settings.model_dim
    num_layers: int = settings.num_layers
    num_heads: int = settings.num_attention_heads
    feedforward_dim: int = settings.feedforward_dim
    dropout: float = settings.dropout_rate
    num_factors: int = 5
    
    def __post_init__(self):
        """Calculate input dimension if not provided."""
        if self.input_dim is None:
            self.input_dim = (
                settings.event_embedding_dim +
                settings.weather_embedding_dim +
                settings.historical_sequence_length * settings.event_embedding_dim +
                settings.temporal_encoding_dim
            )
    
    def validate(self) -> bool:
        """Validate configuration against requirements."""
        if self.num_heads < 4:
            raise ValueError("num_heads must be at least 4 per requirements")
        if self.num_layers < 2:
            raise ValueError("num_layers must be at least 2 per requirements")
        if self.embed_dim % self.num_heads != 0:
            raise ValueError("embed_dim must be divisible by num_heads")
        return True


def create_cat_model(config: ModelConfig = None) -> CATModel:
    """
    Factory function to create a CAT model with default or custom configuration.
    
    Args:
        config: Optional model configuration
        
    Returns:
        Initialized CATModel instance
    """
    config = config or ModelConfig()
    config.validate()
    
    return CATModel(
        input_dim=config.input_dim,
        embed_dim=config.embed_dim,
        num_layers=config.num_layers,
        num_heads=config.num_heads,
        feedforward_dim=config.feedforward_dim,
        dropout=config.dropout,
        num_factors=config.num_factors
    )


def create_tiny_model() -> CATModel:
    """
    Create a small model for testing or quick experimentation.
    
    Returns:
        CATModel with minimal configuration
    """
    return CATModel(
        embed_dim=128,
        num_layers=2,
        num_heads=4,
        feedforward_dim=256,
        num_factors=3
    )


def create_large_model() -> CATModel:
    """
    Create a large model for high-accuracy predictions.
    
    Returns:
        CATModel with maximum configuration
    """
    return CATModel(
        embed_dim=512,
        num_layers=6,
        num_heads=8,
        feedforward_dim=2048,
        num_factors=5
    )