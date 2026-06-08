"""
Transformer Encoder Layer and Stack for the Contextual Availability Transformer (CAT) system.
Implements encoder layers with residual connections and layer normalization.
"""

from typing import List, Optional, Tuple

import torch
import torch.nn as nn
from torch import Tensor

from .attention import MultiHeadAttention
from .feed_forward import FeedForwardNetwork
from ..config import settings


class TransformerEncoderLayer(nn.Module):
    """
    Single Transformer encoder layer.
    
    Combines multi-head self-attention with a feed-forward network,
    using residual connections and layer normalization (requirement 3.2).
    
    Architecture:
        x -> Self-Attention -> Dropout -> Add & LayerNorm -> Feed-Forward -> Dropout -> Add & LayerNorm
    
    Each sublayer has a residual connection around it:
        output = LayerNorm(x + Sublayer(x))
    """
    
    def __init__(
        self,
        embed_dim: int = None,
        num_heads: int = None,
        feedforward_dim: int = None,
        dropout: float = None,
        attention_dropout: float = None
    ):
        """
        Initialize transformer encoder layer.
        
        Args:
            embed_dim: Dimension of embeddings (d_model)
            num_heads: Number of attention heads
            feedforward_dim: Feed-forward hidden dimension (d_ff)
            dropout: Dropout probability for residual connections
            attention_dropout: Dropout probability for attention weights
        """
        super().__init__()
        
        self.embed_dim = embed_dim or settings.model_dim
        self.num_heads = num_heads or settings.num_attention_heads
        self.feedforward_dim = feedforward_dim or settings.feedforward_dim
        self.dropout = dropout or settings.dropout_rate
        self.attention_dropout = attention_dropout or settings.dropout_rate
        
        # Multi-head self-attention sublayer (requirement 3.1)
        self.self_attn = MultiHeadAttention(
            embed_dim=self.embed_dim,
            num_heads=self.num_heads,
            dropout=self.attention_dropout
        )
        
        # Feed-forward sublayer (requirement 3.4)
        self.ffn = FeedForwardNetwork(
            embed_dim=self.embed_dim,
            feedforward_dim=self.feedforward_dim,
            dropout=self.dropout
        )
        
        # Layer normalization after each sublayer (requirement 3.2)
        self.norm1 = nn.LayerNorm(self.embed_dim)
        self.norm2 = nn.LayerNorm(self.embed_dim)
        
        # Dropout for residual connections
        self.dropout_layer = nn.Dropout(self.dropout)
        
        # Store attention weights for interpretability (requirement 7.1)
        self.last_attention_weights: Optional[Tensor] = None
    
    def forward(
        self,
        src: Tensor,
        src_key_padding_mask: Optional[Tensor] = None,
        src_mask: Optional[Tensor] = None
    ) -> Tuple[Tensor, Optional[Tensor]]:
        """
        Apply transformer encoder layer.
        
        Args:
            src: Source tensor [batch_size, seq_len, embed_dim]
            src_key_padding_mask: Padding mask [batch_size, seq_len]
            src_mask: Attention mask [seq_len, seq_len] for causal masking
            
        Returns:
            Tuple of (output tensor, attention weights)
        """
        # Self-attention sublayer with residual connection
        residual = src
        src2, attn_weights = self.self_attn(
            query=src,
            key=src,
            value=src,
            key_padding_mask=src_key_padding_mask,
            attn_mask=src_mask
        )
        
        # Store attention weights for interpretability
        self.last_attention_weights = (
            attn_weights.detach().cpu() if attn_weights is not None else None
        )
        
        # Apply dropout and residual connection, then layer normalization
        src = self.norm1(residual + self.dropout_layer(src2))
        
        # Feed-forward sublayer with residual connection
        residual = src
        src2 = self.ffn(src)
        
        # Apply dropout and residual connection, then layer normalization
        src = self.norm2(residual + self.dropout_layer(src2))
        
        return src, attn_weights
    
    def get_attention_weights(self) -> Optional[Tensor]:
        """Get attention weights from the last forward pass."""
        return self.last_attention_weights


class TransformerEncoder(nn.Module):
    """
    Stack of Transformer encoder layers.
    
    Applies multiple encoder layers sequentially, with attention weights
    collected from all layers for interpretability (requirement 3.8).
    
    Supports configurable layer count (minimum 2 per requirements 3.2).
    """
    
    def __init__(
        self,
        embed_dim: int = None,
        num_layers: int = None,
        num_heads: int = None,
        feedforward_dim: int = None,
        dropout: float = None
    ):
        """
        Initialize transformer encoder stack.
        
        Args:
            embed_dim: Dimension of embeddings
            num_layers: Number of encoder layers (minimum 2 per requirements 3.2)
            num_heads: Number of attention heads per layer
            feedforward_dim: Feed-forward hidden dimension
            dropout: Dropout probability
        """
        super().__init__()
        
        self.embed_dim = embed_dim or settings.model_dim
        self.num_layers = num_layers or settings.num_layers
        self.num_heads = num_heads or settings.num_attention_heads
        self.feedforward_dim = feedforward_dim or settings.feedforward_dim
        self.dropout = dropout or settings.dropout_rate
        
        # Validate minimum layer count (requirement 3.2)
        if self.num_layers < 2:
            raise ValueError(
                f"num_layers ({self.num_layers}) must be at least 2 per requirements"
            )
        
        # Create stack of encoder layers
        self.layers = nn.ModuleList([
            TransformerEncoderLayer(
                embed_dim=self.embed_dim,
                num_heads=self.num_heads,
                feedforward_dim=self.feedforward_dim,
                dropout=self.dropout
            )
            for _ in range(self.num_layers)
        ])
        
        # Final layer normalization
        self.norm = nn.LayerNorm(self.embed_dim)
        
        # Store all attention weights from all layers (requirement 3.8, 7.1)
        self.all_attention_weights: List[Tensor] = []
    
    def forward(
        self,
        src: Tensor,
        src_key_padding_mask: Optional[Tensor] = None,
        src_mask: Optional[Tensor] = None
    ) -> Tuple[Tensor, List[Tensor]]:
        """
        Apply all transformer encoder layers.
        
        Args:
            src: Source tensor [batch_size, seq_len, embed_dim]
            src_key_padding_mask: Padding mask [batch_size, seq_len]
            src_mask: Attention mask [seq_len, seq_len]
            
        Returns:
            Tuple of (output tensor, list of attention weights from each layer)
        """
        self.all_attention_weights = []
        
        output = src
        
        # Pass through each encoder layer
        for layer in self.layers:
            output, attn_weights = layer(
                output,
                src_key_padding_mask=src_key_padding_mask,
                src_mask=src_mask
            )
            
            # Collect attention weights from each layer
            if attn_weights is not None:
                self.all_attention_weights.append(attn_weights)
        
        # Apply final layer normalization
        output = self.norm(output)
        
        return output, self.all_attention_weights
    
    def get_all_attention_weights(self) -> List[Tensor]:
        """Get attention weights from all layers for interpretability."""
        return self.all_attention_weights
    
    def get_num_layers(self) -> int:
        """Get the number of layers in the encoder."""
        return self.num_layers