"""
Contextual Availability Transformer (CAT)
A machine learning system for predicting availability patterns based on contextual factors.
"""

__version__ = "1.0.0"

# Import main components
from . import models
from . import preprocessing
from . import data_collection
from . import inference
from . import training
from . import interpretability
from . import serialization
from . import utils

__all__ = [
    "models",
    "preprocessing",
    "data_collection",
    "inference",
    "training",
    "interpretability",
    "serialization",
    "utils",
]