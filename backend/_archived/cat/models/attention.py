"""
Multi-head Attention Mechanism for the Contextual Availability Transformer (CAT) system.
Implements scaled dot-product attention with configurable head count and mask handling.
"""

import math
from typing import Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor

from ..config import settings


class MultiHeadAttention(nn.Module):
    """
    Multi-head self-attention mechanism.
    
    This implementation follows the scaled dot-product attention from the
    "Attention Is All You Need" paper, with support for configurable attention
    heads and attention masking for variable-length sequences.
    
    Supports:
    - Configurable number of attention heads (minimum 4 per requirements)
    - Query, key, value projections with learnable weights
    - Attention mask handling for variable-length sequences
    - Attention weight extraction for interpretability
    """
    
    def __init__(
        self,
        embed_dim: int = None,
        num_heads: int = None,
        dropout: float = None,
        bias: bool = True
    ):
        """
        Initialize multi-head attention.
        
        Args:
            embed_dim: Dimension of input embeddings (must be divisible by num_heads)
            num_heads: Number of attention heads (minimum 4 per requirements 3.1)
            dropout: Dropout probability for attention weights
            bias: Whether to include bias terms in linear projections
            
        Raises:
            ValueError: If embed_dim is not divisible by num_heads
        """
        super().__init__()
        
        self.embed_dim = embed_dim or settings.model_dim
        self.num_heads = num_heads or settings.num_attention_heads
        self.head_dim = self.embed_dim // self.num_heads
        self.dropout = dropout or settings.dropout_rate
        
        if self.embed_dim % self.num_heads != 0:
            raise ValueError(
                f"embed_dim ({self.embed_dim}) must be divisible by "
                f"num_heads ({self.num_heads})"
            )
        
        # Linear projections for query, key, value
        self.q_proj = nn.Linear(self.embed_dim, self.embed_dim, bias=bias)
        self.k_proj = nn.Linear(self.embed_dim, self.embed_dim, bias=bias)
        self.v_proj = nn.Linear(self.embed_dim, self.embed_dim, bias=bias)
        
        # Output projection
        self.out_proj = nn.Linear(self.embed_dim, self.embed_dim, bias=bias)
        
        # Dropout for attention weights
        self.attn_dropout = nn.Dropout(self.dropout)
        
        # Store attention weights for interpretability (requirement 3.6, 7.1)
        self.last_attention_weights: Optional[Tensor] = None
        self.register_buffer("_none_mask", torch.tensor(1.0))
    
    def forward(
        self,
        query: Tensor,
        key: Tensor,
        value: Tensor,
        key_padding_mask: Optional[Tensor] = None,
        attn_mask: Optional[Tensor] = None,
        need_weights: bool = True
    ) -> Tuple[Tensor, Optional[Tensor]]:
        """
        Compute multi-head attention.
        
        Args:
            query: Query tensor [batch_size, seq_len, embed_dim]
            key: Key tensor [batch_size, seq_len, embed_dim]
            value: Value tensor [batch_size, seq_len, embed_dim]
            key_padding_mask: Padding mask [batch_size, seq_len] (1 = valid, 0 = padding)
            attn_mask: Attention mask [seq_len, seq_len] for causal masking
            need_weights: Whether to return attention weights
            
        Returns:
            Tuple of (output tensor, attention weights tensor or None)
        """
        batch_size, seq_len, _ = query.shape
        
        # Linear projections and reshape for multi-head processing
        # Shape: [batch_size, num_heads, seq_len, head_dim]
        q = self.q_proj(query).view(batch_size, seq_len, self.num_heads, self.head_dim).transpose(1, 2)
        k = self.k_proj(key).view(batch_size, seq_len, self.num_heads, self.head_dim).transpose(1, 2)
        v = self.v_proj(value).view(batch_size, seq_len, self.num_heads, self.head_dim).transpose(1, 2)
        
        # Scaled dot-product attention
        # Scale by sqrt(head_dim) for numerical stability
        scale = math.sqrt(self.head_dim)
        attn_scores = torch.matmul(q, k.transpose(-2, -1)) / scale
        
        # Apply attention mask for variable-length sequences (requirement 3.7)
        if attn_mask is not None:
            attn_scores = attn_scores.masked_fill(attn_mask == 0, float('-inf'))
        
        # Apply key padding mask
        if key_padding_mask is not None:
            attn_scores = attn_scores.masked_fill(
                key_padding_mask.unsqueeze(1).unsqueeze(2) == 0,
                float('-inf')
            )
        
        # Softmax to produce valid probability distributions (rows sum to 1)
        attn_weights = F.softmax(attn_scores, dim=-1)
        
        # Apply dropout only during training
        if self.training:
            attn_weights = self.attn_dropout(attn_weights)
        
        # Store attention weights for interpretability (requirement 7.1)
        # Store before dropout for valid probability distributions
        if need_weights:
            self.last_attention_weights = F.softmax(attn_scores, dim=-1).detach().cpu()
        
        # Apply attention to values
        output = torch.matmul(attn_weights, v)
        
        # Reshape output: [batch_size, seq_len, embed_dim]
        output = output.transpose(1, 2).contiguous().view(batch_size, seq_len, self.embed_dim)
        
        # Final output projection
        output = self.out_proj(output)
        
        return output, attn_weights if need_weights else None
    
    def get_attention_weights(self) -> Tensor:
        """
        Get the attention weights from the last forward pass.
        
        Returns:
            Attention weights tensor [batch_size, num_heads, seq_len, seq_len]
            
        Raises:
            RuntimeError: If no forward pass has been run yet
        """
        if self.last_attention_weights is None:
            raise RuntimeError(
                "No attention weights available. Run forward pass first with need_weights=True."
            )
        return self.last_attention_weights
    
    def get_attention_weights_per_head(self) -> Tensor:
        """
        Get attention weights organized per head for analysis.
        
        Returns:
            Attention weights per head [num_heads, batch_size, seq_len, seq_len]
        """
        weights = self.get_attention_weights()
        return weights.permute(1, 0, 2, 3)  # [num_heads, batch_size, seq_len, seq_len]