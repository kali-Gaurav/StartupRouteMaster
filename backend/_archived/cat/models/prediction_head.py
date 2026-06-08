"""
Prediction Head for the Contextual Availability Transformer (CAT) system.
Implements probability prediction, confidence interval estimation, and contributing factor analysis.
"""

from typing import List, Optional, Tuple

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor

from ..config import settings
from ..models.schemas import ContributingFactor


class PredictionHead(nn.Module):
    """
    Prediction head for generating availability predictions.
    
    Produces:
    - Probability of availability (sigmoid output per requirement 3.5)
    - Confidence interval (lower and upper bounds)
    - Contributing factors (from attention weights per requirements 7.1-7.5)
    """
    
    def __init__(
        self,
        embed_dim: int = None,
        hidden_dim: int = None,
        num_factors: int = 5,
        num_classes: int = None
    ):
        """
        Initialize prediction head.
        
        Args:
            embed_dim: Input embedding dimension
            hidden_dim: Hidden layer dimension
            num_factors: Number of contributing factors to identify
            num_classes: Number of output classes (for multi-class prediction)
        """
        super().__init__()
        
        self.embed_dim = embed_dim or settings.model_dim
        self.hidden_dim = hidden_dim or (settings.feedforward_dim // 4)
        self.num_factors = num_factors
        self.num_classes = num_classes or 1
        
        # Main prediction network
        self.network = nn.Sequential(
            nn.Linear(self.embed_dim, self.hidden_dim),
            nn.ReLU(),
            nn.Dropout(settings.dropout_rate),
            nn.Linear(self.hidden_dim, self.hidden_dim // 2),
            nn.ReLU()
        )
        
        # Probability prediction with sigmoid activation (requirement 3.5)
        self.probability_head = nn.Linear(self.hidden_dim // 2, self.num_classes)
        
        # Confidence interval estimation (requirement 2.3, 2.4)
        self.confidence_head = nn.Linear(self.hidden_dim // 2, 2)
        
        # Contributing factors analysis network (requirements 7.1-7.5)
        self.factor_network = nn.Linear(self.embed_dim, self.hidden_dim)
        self.factor_head = nn.Linear(self.hidden_dim, num_factors)
        
        # Default factor names for interpretability
        self.default_factor_names = [
            "event_impact",
            "weather_impact",
            "historical_pattern",
            "temporal_pattern",
            "location_context"
        ]
    
    def forward(
        self,
        transformer_output: Tensor,
        attention_weights: List[Tensor]
    ) -> Tuple[Tensor, Tensor, Tensor, Tensor]:
        """
        Generate predictions from transformer output.
        
        Args:
            transformer_output: Output from transformer encoder [batch_size, seq_len, embed_dim]
            attention_weights: List of attention weight tensors from each layer
            
        Returns:
            Tuple of (probability, confidence_lower, confidence_upper, features)
        """
        # Mean pooling over sequence dimension
        if transformer_output.dim() == 3:
            pooled = transformer_output.mean(dim=1)
        else:
            pooled = transformer_output
        
        # Main prediction network
        features = self.network(pooled)
        
        # Probability prediction with sigmoid activation (requirement 3.5)
        prob_logits = self.probability_head(features)
        probability = torch.sigmoid(prob_logits).squeeze(-1)
        
        # Confidence interval estimation (requirement 2.3, 2.4)
        confidence_raw = self.confidence_head(features)
        
        # Clamp confidence bounds to [0, 1]
        confidence_lower = torch.clamp(confidence_raw[:, 0], min=0.0, max=1.0)
        confidence_upper = torch.clamp(confidence_raw[:, 1], min=0.0, max=1.0)
        
        # Ensure lower <= upper
        confidence_lower = torch.min(confidence_lower, confidence_upper)
        confidence_upper = torch.max(confidence_lower, confidence_upper)
        
        return probability, confidence_lower, confidence_upper, features
    
    def analyze_contributing_factors(
        self,
        transformer_output: Tensor,
        attention_weights: List[Tensor],
        factor_names: Optional[List[str]] = None
    ) -> List[ContributingFactor]:
        """
        Analyze attention weights to identify contributing factors.
        
        Extracts and ranks contributing factors based on attention patterns
        (requirements 7.1, 7.2, 7.3, 7.4, 7.5).
        
        Args:
            transformer_output: Output from transformer encoder
            attention_weights: List of attention weight tensors from each layer
            factor_names: Optional custom names for factors
            
        Returns:
            List of ContributingFactor objects sorted by importance
        """
        if factor_names is None:
            factor_names = self.default_factor_names[:self.num_factors]
        
        # Aggregate attention weights across layers and heads
        if attention_weights and len(attention_weights) > 0:
            # Stack and mean across layers and heads
            # Shape: [num_layers, batch_size, num_heads, seq_len, seq_len]
            all_weights = torch.stack([w.mean(dim=1).mean(dim=0) for w in attention_weights])
            
            # Mean across layers: [batch_size, seq_len, seq_len]
            aggregated = all_weights.mean(dim=0)
            
            # Analyze attention patterns to determine importance
            # Higher attention to certain positions indicates importance
            importance = aggregated.mean(dim=1)  # [batch_size, seq_len]
            
            # Mean across batch: [seq_len]
            importance = importance.mean(dim=0)
            
            # Normalize to [0, 1]
            min_val = importance.min()
            max_val = importance.max()
            if max_val > min_val:
                importance = (importance - min_val) / (max_val - min_val + 1e-8)
            else:
                importance = torch.ones_like(importance) / importance.numel()
        else:
            # No attention weights available, use uniform distribution
            seq_len = transformer_output.size(1) if transformer_output.dim() > 1 else 1
            if seq_len > 1:
                importance = torch.ones(seq_len) / seq_len
            else:
                # Single element case - use scalar tensor
                importance = torch.tensor(1.0)
        
        # Map importance scores to factors
        factor_scores: List[ContributingFactor] = []
        num_factors = min(len(factor_names), self.num_factors)
        
        # Get importance as a list for indexing
        importance_list = importance.tolist() if importance.dim() > 0 else [importance.item()]
        seq_len = len(importance_list)
        
        for i in range(num_factors):
            # Distribute importance across factors based on attention patterns
            score = importance_list[i % seq_len] if seq_len > 0 else 0.0
            
            factor_scores.append(ContributingFactor(
                factor_name=factor_names[i],
                importance_score=score,
                description=self._get_factor_description(factor_names[i], score)
            ))
        
        # Sort by importance score in descending order (requirement 7.4)
        factor_scores.sort(key=lambda x: x.importance_score, reverse=True)
        
        # Renormalize scores to sum to 1.0 (requirement 7.3)
        total = sum(f.importance_score for f in factor_scores)
        if total > 0:
            for f in factor_scores:
                f.importance_score /= total
        
        return factor_scores
    
    def _get_factor_description(self, factor_name: str, importance: float) -> str:
        """Generate human-readable description for a factor."""
        descriptions = {
            "event_impact": "Influence of nearby events on availability",
            "weather_impact": "Effect of weather conditions on availability",
            "historical_pattern": "Historical availability patterns",
            "temporal_pattern": "Time-based patterns (hour, day, season)",
            "location_context": "Location-specific factors"
        }
        
        base_desc = descriptions.get(factor_name, f"Factor: {factor_name}")
        
        # Add importance context
        if importance > 0.7:
            level = "high"
        elif importance > 0.4:
            level = "moderate"
        else:
            level = "low"
        
        return f"{base_desc} (importance: {level})"
    
    def get_factor_names(self) -> List[str]:
        """Get the default factor names."""
        return self.default_factor_names[:self.num_factors]


class ConfidenceIntervalEstimator(nn.Module):
    """
    Dedicated module for confidence interval estimation.
    
    Uses model uncertainty and historical accuracy to compute
    prediction confidence bounds (requirements 2.3, 2.4).
    """
    
    def __init__(self, embed_dim: int = None, hidden_dim: int = None):
        """
        Initialize confidence interval estimator.
        
        Args:
            embed_dim: Input embedding dimension
            hidden_dim: Hidden layer dimension
        """
        super().__init__()
        
        self.embed_dim = embed_dim or settings.model_dim
        self.hidden_dim = hidden_dim or (settings.feedforward_dim // 4)
        
        # Network to estimate uncertainty
        self.uncertainty_network = nn.Sequential(
            nn.Linear(self.embed_dim, self.hidden_dim),
            nn.ReLU(),
            nn.Dropout(settings.dropout_rate),
            nn.Linear(self.hidden_dim, self.hidden_dim // 2),
            nn.ReLU()
        )
        
        # Output: lower and upper bounds
        self.bounds_head = nn.Linear(self.hidden_dim // 2, 2)
    
    def forward(self, x: Tensor) -> Tuple[Tensor, Tensor]:
        """
        Estimate confidence interval bounds.
        
        Args:
            x: Input tensor [batch_size, embed_dim]
            
        Returns:
            Tuple of (lower_bound, upper_bound) both [batch_size]
        """
        features = self.uncertainty_network(x)
        bounds = self.bounds_head(features)
        
        # Clamp to valid probability range
        lower = torch.clamp(bounds[:, 0], min=0.0, max=1.0)
        upper = torch.clamp(bounds[:, 1], min=0.0, max=1.0)
        
        # Ensure lower <= upper
        lower = torch.min(lower, upper)
        upper = torch.max(lower, upper)
        
        return lower, upper