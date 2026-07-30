"""
Shim module for CancellationPredictor to maintain compatibility.
The actual implementation is in services.ml.cancellation.
"""

from services.ml.cancellation import (
    CancellationPredictor,
    CancellationPrediction,
    cancellation_predictor
)

__all__ = [
    "CancellationPredictor",
    "CancellationPrediction",
    "cancellation_predictor"
]
