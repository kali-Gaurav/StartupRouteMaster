"""
Transformer Model for CAT.

This module implements the core Transformer-based neural network:
- Multi-head self-attention
- Feed-forward networks
- Layer normalization
- Residual connections
- Prediction head
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from typing import List, Tuple, Optional
from dataclasses import dataclass
import logging

from .data_models import ModelInput, AvailabilityPrediction

logger = logging.getLogger(__name__)


@dataclass
class ModelConfig:
    """Configuration for the CAT model."""
    event_embedding_dim: int = 128
    weather_embedding_dim: int = 64
    historical_sequence_length: int = 24
    historical_embedding_dim: int = 5
    temporal_encoding_dim: int = 32
    model_dim: int = 256
    num_layers: int = 6
    num_heads: int = 8
    feedforward_dim: int = 512
    dropout: float = 0.1
    max_position_embeddings: int = 100


class MultiHeadAttention(nn.Module):
    """Multi-head self-attention mechanism."""
    
    def __init__(self, model_dim: int, num_heads: int, dropout: float = 0.1):
        super().__init__()
        self.model_dim = model_dim
        self.num_heads = num_heads
        self.head_dim = model_dim // num_heads
        
        assert self.head_dim * num_heads == model_dim, "model_dim must be divisible by num_heads"
        
        self.query_proj = nn.Linear(model_dim, model_dim)
        self.key_proj = nn.Linear(model_dim, model_dim)
        self.value_proj = nn.Linear(model_dim, model_dim)
        self.output_proj = nn.Linear(model_dim, model_dim)
        self.dropout = nn.Dropout(dropout)
    
    def forward(self, query: torch.Tensor, key: torch.Tensor, value: torch.Tensor,
                attention_mask: Optional[torch.Tensor] = None) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass for multi-head attention.
        
        Args:
            query: Query tensor of shape (batch, seq_len, model_dim)
            key: Key tensor of shape (batch, seq_len, model_dim)
            value: Value tensor of shape (batch, seq_len, model_dim)
            attention_mask: Optional mask of shape (batch, seq_len, seq_len)
            
        Returns:
            Output tensor and attention weights
        """
        batch_size = query.size(0)
        
        # Project to query, key, value
        Q = self.query_proj(query)
        K = self.key_proj(key)
        V = self.value_proj(value)
        
        # Split into heads
        Q = Q.view(batch_size, -1, self.num_heads, self.head_dim).transpose(1, 2)
        K = K.view(batch_size, -1, self.num_heads, self.head_dim).transpose(1, 2)
        V = V.view(batch_size, -1, self.num_heads, self.head_dim).transpose(1, 2)
        
        # Scaled dot-product attention
        attention_scores = torch.matmul(Q, K.transpose(-2, -1)) / torch.sqrt(torch.tensor(self.head_dim, dtype=torch.float32))
        
        if attention_mask is not None:
            attention_scores = attention_scores.masked_fill(attention_mask == 0, -1e9)
        
        attention_weights = F.softmax(attention_scores, dim=-1)
        attention_weights = self.dropout(attention_weights)
        
        attention_output = torch.matmul(attention_weights, V)
        
        # Concatenate heads
        attention_output = attention_output.transpose(1, 2).contiguous()
        attention_output = attention_output.view(batch_size, -1, self.model_dim)
        
        # Final projection
        output = self.output_proj(attention_output)
        
        return output, attention_weights


class FeedForwardNetwork(nn.Module):
    """Feed-forward network with two linear layers."""
    
    def __init__(self, model_dim: int, feedforward_dim: int, dropout: float = 0.1):
        super().__init__()
        self.linear1 = nn.Linear(model_dim, feedforward_dim)
        self.linear2 = nn.Linear(feedforward_dim, model_dim)
        self.dropout = nn.Dropout(dropout)
    
    def forward(self, x: torch.Tensor) -> torch.Tensor:
        """Forward pass for feed-forward network."""
        output = self.linear1(x)
        output = F.relu(output)
        output = self.dropout(output)
        output = self.linear2(output)
        return output


class TransformerEncoderLayer(nn.Module):
    """Single Transformer encoder layer."""
    
    def __init__(self, model_dim: int, num_heads: int, feedforward_dim: int, dropout: float = 0.1):
        super().__init__()
        self.self_attn = MultiHeadAttention(model_dim, num_heads, dropout)
        self.ffn = FeedForwardNetwork(model_dim, feedforward_dim, dropout)
        self.norm1 = nn.LayerNorm(model_dim)
        self.norm2 = nn.LayerNorm(model_dim)
        self.dropout = nn.Dropout(dropout)
    
    def forward(self, x: torch.Tensor, attention_mask: Optional[torch.Tensor] = None) -> Tuple[torch.Tensor, torch.Tensor]:
        """
        Forward pass for transformer encoder layer.
        
        Args:
            x: Input tensor
            attention_mask: Optional attention mask
            
        Returns:
            Output tensor and attention weights
        """
        # Self-attention sublayer with residual connection
        attention_output, attention_weights = self.self_attn(x, x, x, attention_mask)
        x = self.norm1(x + self.dropout(attention_output))
        
        # Feed-forward sublayer with residual connection
        ffn_output = self.ffn(x)
        x = self.norm2(x + self.dropout(ffn_output))
        
        return x, attention_weights


class TransformerEncoder(nn.Module):
    """Stack of Transformer encoder layers."""
    
    def __init__(self, config: ModelConfig):
        super().__init__()
        self.layers = nn.ModuleList([
            TransformerEncoderLayer(
                config.model_dim,
                config.num_heads,
                config.feedforward_dim,
                config.dropout
            )
            for _ in range(config.num_layers)
        ])
    
    def forward(self, x: torch.Tensor) -> Tuple[torch.Tensor, List[torch.Tensor]]:
        """
        Forward pass for transformer encoder stack.
        
        Args:
            x: Input tensor
            
        Returns:
            Output tensor and list of attention weights from each layer
        """
        attention_weights = []
        
        for layer in self.layers:
            x, weights = layer(x)
            attention_weights.append(weights)
        
        return x, attention_weights


class CATModel(nn.Module):
    """
    Contextual Availability Transformer (CAT) model.
    
    Combines all components to produce availability predictions.
    """
    
    def __init__(self, config: ModelConfig = None):
        """
        Initialize the CAT model.
        
        Args:
            config: ModelConfig with model parameters
        """
        super().__init__()
        self.config = config or ModelConfig()
        
        # Input projection
        input_dim = (
            self.config.event_embedding_dim +
            self.config.weather_embedding_dim +
            self.config.historical_sequence_length * self.config.historical_embedding_dim +
            self.config.temporal_encoding_dim
        )
        
        self.input_projection = nn.Linear(input_dim, self.config.model_dim)
        
        # Transformer encoder
        self.encoder = TransformerEncoder(self.config)
        
        # Prediction head
        self.prediction_head = nn.Sequential(
            nn.Linear(self.config.model_dim, self.config.model_dim // 2),
            nn.ReLU(),
            nn.Dropout(self.config.dropout),
            nn.Linear(self.config.model_dim // 2, 1),
            nn.Sigmoid(),
        )
        
        # Confidence estimation
        self.confidence_head = nn.Sequential(
            nn.Linear(self.config.model_dim, self.config.model_dim // 2),
            nn.ReLU(),
            nn.Dropout(self.config.dropout),
            nn.Linear(self.config.model_dim // 2, 2),
        )
        
        # Initialize weights
        self._initialize_weights()
    
    def _initialize_weights(self):
        """Initialize model weights."""
        for module in self.modules():
            if isinstance(module, nn.Linear):
                nn.init.xavier_uniform_(module.weight)
                if module.bias is not None:
                    nn.init.zeros_(module.bias)
    
    def forward(self, model_input: ModelInput) -> AvailabilityPrediction:
        """
        Forward pass for the CAT model.
        
        Args:
            model_input: ModelInput with encoded tensors
            
        Returns:
            AvailabilityPrediction with probability and confidence
        """
        # Convert all inputs to tensors
        event_tensor = torch.tensor(model_input.event_embeddings, dtype=torch.float32)
        weather_tensor = torch.tensor(model_input.weather_embeddings, dtype=torch.float32)
        historical_tensor = torch.tensor(model_input.historical_sequence, dtype=torch.float32)
        temporal_tensor = torch.tensor(model_input.temporal_encoding, dtype=torch.float32)
        
        # Flatten all tensors to 1D and concatenate
        event_flat = event_tensor.view(-1)
        weather_flat = weather_tensor.view(-1)
        historical_flat = historical_tensor.view(-1)
        temporal_flat = temporal_tensor.view(-1)
        
        # Concatenate all inputs along feature dimension
        combined = torch.cat([event_flat, weather_flat, historical_flat, temporal_flat])
        
        # Add batch dimension
        combined = combined.unsqueeze(0)
        
        # Project to model dimension
        x = self.input_projection(combined)
        
        # Pass through transformer encoder
        x, attention_weights = self.encoder(x)
        
        # Use the first token for prediction (similar to [CLS] token)
        x = x[:, 0, :]
        
        # Generate prediction
        raw_pred = self.prediction_head(x)
        probability = torch.sigmoid(raw_pred).squeeze(0).item()
        
        # Clamp to valid range
        probability = max(0.0, min(1.0, probability))
        
        # Generate confidence interval
        confidence_output = self.confidence_head(x).squeeze(0)
        lower = max(0.0, min(1.0, probability - 0.1))
        upper = max(0.0, min(1.0, probability + 0.1))
        
        # Identify contributing factors from attention weights
        contributing_factors = self._analyze_attention_weights(attention_weights)
        
        return AvailabilityPrediction(
            probability=probability,
            confidence_interval=(lower, upper),
            contributing_factors=contributing_factors,
        )
    
    def _analyze_attention_weights(self, attention_weights: List[torch.Tensor]) -> List[Tuple[str, float]]:
        """
        Analyze attention weights to identify contributing factors.
        
        Args:
            attention_weights: List of attention weight tensors from each layer
            
        Returns:
            List of (factor_name, importance_score) tuples
        """
        # Simple analysis: average attention across all heads and layers
        if not attention_weights:
            return [
                ("event_calendar", 0.3),
                ("weather", 0.3),
                ("historical", 0.3),
                ("temporal", 0.1),
            ]
        
        # Average attention weights
        avg_weights = torch.mean(torch.stack(attention_weights), dim=0)
        
        # Get sequence length from attention weights
        seq_len = avg_weights.size(-1)
        
        # Calculate importance scores based on available positions
        # For single-token input, use uniform distribution
        if seq_len < 4:
            return [
                ("event_calendar", 0.3),
                ("weather", 0.3),
                ("historical", 0.3),
                ("temporal", 0.1),
            ]
        
        # For longer sequences, use actual attention weights
        event_importance = avg_weights[0, 0, 0].item()
        weather_importance = avg_weights[0, 0, 1].item()
        historical_importance = avg_weights[0, 0, 2].item()
        temporal_importance = avg_weights[0, 0, 3].item()
        
        # Normalize to sum to 1
        total = event_importance + weather_importance + historical_importance + temporal_importance
        if total > 0:
            event_importance /= total
            weather_importance /= total
            historical_importance /= total
            temporal_importance /= total
        
        factors = [
            ("event_calendar", round(event_importance, 2)),
            ("weather", round(weather_importance, 2)),
            ("historical", round(historical_importance, 2)),
            ("temporal", round(temporal_importance, 2)),
        ]
        
        # Sort by importance
        factors.sort(key=lambda x: x[1], reverse=True)
        
        return factors
    
    def save(self, path: str):
        """Save model to file."""
        torch.save({
            'config': self.config,
            'state_dict': self.state_dict(),
        }, path)
    
    @classmethod
    def load(cls, path: str) -> 'CATModel':
        """Load model from file."""
        checkpoint = torch.load(path, map_location='cpu')
        config = checkpoint['config']
        model = cls(config)
        model.load_state_dict(checkpoint['state_dict'])
        return model