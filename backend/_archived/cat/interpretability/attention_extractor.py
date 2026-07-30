"""
Attention weight extraction and aggregation for the CAT system.

This module provides functionality to:
- Extract attention weights from all layers during inference
- Store attention weights with prediction results
- Aggregate attention weights across heads for interpretability
"""

from dataclasses import dataclass
from typing import List, Optional, Tuple

import torch
from torch import Tensor

from ..models.transformer import CATModel, TransformerEncoder


@dataclass
class AttentionWeights:
    """
    Container for attention weights from a single inference call.
    
    Attributes:
        layer_weights: List of attention weights for each transformer layer
            Each tensor has shape [batch_size, num_heads, seq_len, seq_len]
        aggregated_weights: Mean attention weights across all layers and heads
            Shape [seq_len, seq_len]
        head_weights: List of weights per head per layer for detailed analysis
    """
    layer_weights: List[Tensor]
    aggregated_weights: Tensor
    head_weights: Optional[List[List[Tensor]]] = None


class AttentionExtractor:
    """
    Extracts and aggregates attention weights from the CAT model.
    
    This class provides methods to:
    - Extract attention weights from all transformer layers
    - Aggregate weights across attention heads
    - Store weights for later analysis
    """
    
    def __init__(self, model: CATModel):
        """
        Initialize the attention extractor.
        
        Args:
            model: The CAT model to extract attention weights from
        """
        self.model = model
        self._last_attention_weights: Optional[AttentionWeights] = None
    
    def extract_attention_weights(
        self,
        input_tensor: Tensor,
        return_head_weights: bool = False
    ) -> AttentionWeights:
        """
        Extract attention weights from all layers during inference.
        
        Args:
            input_tensor: Input tensor [batch_size, input_dim]
            return_head_weights: Whether to return per-head weights
            
        Returns:
            AttentionWeights object containing all extracted weights
        """
        # Ensure model is in eval mode
        self.model.eval()
        
        with torch.no_grad():
            # Forward pass with return_factors=True to get attention weights
            output = self.model(input_tensor, return_factors=True)
            
            # Get attention weights from the model
            layer_weights = output.get("attention_weights", [])
            
            if not layer_weights:
                raise ValueError("No attention weights found in model output")
            
            # Aggregate weights across layers and heads
            aggregated = self._aggregate_weights(layer_weights)
            
            # Optionally store per-head weights
            head_weights = None
            if return_head_weights:
                head_weights = self._extract_head_weights(layer_weights)
            
            attention_weights = AttentionWeights(
                layer_weights=layer_weights,
                aggregated_weights=aggregated,
                head_weights=head_weights
            )
            
            # Store for later retrieval
            self._last_attention_weights = attention_weights
            
            return attention_weights
    
    def _aggregate_weights(self, layer_weights: List[Tensor]) -> Tensor:
        """
        Aggregate attention weights across all layers and heads.
        
        Args:
            layer_weights: List of attention weight tensors from each layer
                Each tensor has shape [batch_size, num_heads, seq_len, seq_len]
                
        Returns:
            Aggregated weights tensor [seq_len, seq_len]
        """
        if not layer_weights:
            raise ValueError("No layer weights provided")
        
        # Stack all layer weights
        stacked = torch.stack(layer_weights)  # [num_layers, batch_size, num_heads, seq_len, seq_len]
        
        # Mean across batch, layers, and heads
        # Result: [seq_len, seq_len]
        aggregated = stacked.mean(dim=[0, 1, 2])
        
        return aggregated
    
    def _extract_head_weights(self, layer_weights: List[Tensor]) -> List[List[Tensor]]:
        """
        Extract attention weights per head per layer.
        
        Args:
            layer_weights: List of attention weight tensors from each layer
                Each tensor has shape [batch_size, num_heads, seq_len, seq_len]
                
        Returns:
            List of lists: [layer][head][seq_len, seq_len]
        """
        head_weights = []
        
        for layer_idx, layer_weights_tensor in enumerate(layer_weights):
            # layer_weights_tensor: [batch_size, num_heads, seq_len, seq_len]
            batch_size, num_heads, seq_len, _ = layer_weights_tensor.shape
            
            # Extract per-head weights
            layer_head_weights = []
            for head_idx in range(num_heads):
                # Get weights for this head: [batch_size, seq_len, seq_len]
                head_weights_tensor = layer_weights_tensor[:, head_idx, :, :]
                
                # Mean across batch
                mean_head_weights = head_weights_tensor.mean(dim=0)
                layer_head_weights.append(mean_head_weights)
            
            head_weights.append(layer_head_weights)
        
        return head_weights
    
    def get_last_attention_weights(self) -> Optional[AttentionWeights]:
        """Get the last extracted attention weights."""
        return self._last_attention_weights
    
    def validate_attention_weights(self, weights: AttentionWeights) -> bool:
        """
        Validate that attention weights form valid probability distributions.
        
        Args:
            weights: AttentionWeights object to validate
            
        Returns:
            True if all weights are valid, False otherwise
        """
        # Check that each layer's weights sum to 1 along the attention dimension
        for layer_idx, layer_weights in enumerate(weights.layer_weights):
            # layer_weights: [batch_size, num_heads, seq_len, seq_len]
            weight_sums = layer_weights.sum(dim=-1)  # [batch_size, num_heads, seq_len]
            
            # Check if sums are close to 1
            if not torch.allclose(weight_sums, torch.ones_like(weight_sums), atol=1e-5):
                return False
        
        return True


def extract_and_aggregate_attention(
    model: CATModel,
    input_tensor: Tensor
) -> Tuple[Tensor, List[Tensor]]:
    """
    Convenience function to extract and aggregate attention weights.
    
    Args:
        model: The CAT model
        input_tensor: Input tensor [batch_size, input_dim]
        
    Returns:
        Tuple of (aggregated_weights, layer_weights)
    """
    extractor = AttentionExtractor(model)
    attention_weights = extractor.extract_attention_weights(input_tensor)
    
    return attention_weights.aggregated_weights, attention_weights.layer_weights


def get_attention_visualization_data(
    model: CATModel,
    input_tensor: Tensor
) -> dict:
    """
    Get attention weights formatted for visualization.
    
    Args:
        model: The CAT model
        input_tensor: Input tensor [batch_size, input_dim]
        
    Returns:
        Dictionary with visualization-ready data:
        - layer_weights: List of [num_heads, seq_len, seq_len] tensors
        - aggregated: [seq_len, seq_len] tensor
        - head_weights: List of [num_heads][seq_len, seq_len] tensors
    """
    extractor = AttentionExtractor(model)
    attention_weights = extractor.extract_attention_weights(input_tensor, return_head_weights=True)
    
    # Convert layer weights to visualization format
    layer_weights_viz = []
    for layer_weights in attention_weights.layer_weights:
        # [batch_size, num_heads, seq_len, seq_len] -> [num_heads, seq_len, seq_len]
        mean_layer_weights = layer_weights.mean(dim=0)
        layer_weights_viz.append(mean_layer_weights)
    
    return {
        "layer_weights": layer_weights_viz,
        "aggregated": attention_weights.aggregated_weights,
        "head_weights": attention_weights.head_weights,
    }
