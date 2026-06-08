"""
Feed-Forward Network Layer for the Contextual Availability Transformer (CAT) system.
Implements position-wise feed-forward network with ReLU activation and dropout.
"""

from typing import Optional

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor

from ..config import settings


class FeedForwardNetwork(nn.Module):
    """
    Position-wise feed-forward network.
    
    This is applied to each position separately and identically.
    It consists of two linear transformations with a ReLU activation in between,
    followed by dropout for regularization (requirement 3.4).
    
    Architecture:
        x -> Linear(d_model, d_ff) -> ReLU -> Dropout -> Linear(d_ff, d_model) -> output
    """
    
    def __init__(
        self,
        embed_dim: int = None,
        feedforward_dim: int = None,
        dropout: float = None,
        activation: str = "relu"
    ):
        """
        Initialize feed-forward network.
        
        Args:
            embed_dim: Input and output dimension (d_model)
            feedforward_dim: Hidden dimension (d_ff)
            dropout: Dropout probability for regularization
            activation: Activation function ("relu" or "gelu")
        """
        super().__init__()
        
        self.embed_dim = embed_dim or settings.model_dim
        self.feedforward_dim = feedforward_dim or settings.feedforward_dim
        self.dropout = dropout or settings.dropout_rate
        self.activation = activation
        
        # First linear transformation: d_model -> d_ff
        self.linear1 = nn.Linear(self.embed_dim, self.feedforward_dim)
        
        # Second linear transformation: d_ff -> d_model
        self.linear2 = nn.Linear(self.feedforward_dim, self.embed_dim)
        
        # Dropout layer for regularization
        self.dropout_layer = nn.Dropout(self.dropout)
    
    def forward(self, x: Tensor) -> Tensor:
        """
        Apply feed-forward network.
        
        Args:
            x: Input tensor [batch_size, seq_len, embed_dim]
            
        Returns:
            Output tensor [batch_size, seq_len, embed_dim]
        """
        # First linear transformation
        x = self.linear1(x)
        
        # Apply activation function
        if self.activation == "relu":
            x = F.relu(x)
        elif self.activation == "gelu":
            x = F.gelu(x)
        else:
            raise ValueError(f"Unknown activation: {self.activation}")
        
        # Apply dropout
        x = self.dropout_layer(x)
        
        # Second linear transformation
        x = self.linear2(x)
        
        return x
    
    def get_hidden_dim(self) -> int:
        """Get the feedforward hidden dimension."""
        return self.feedforward_dim
    
    def get_output_dim(self) -> int:
        """Get the input/output dimension."""
        return self.embed_dim