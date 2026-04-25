import math
import logging
from typing import Dict, Tuple, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class ReliabilityEngine:
    """
    [Subtask A2.1] Stochastic Reliability Engine.
    Predicts connection success probability using Gaussian delay distributions.
    """
    
    # Default distributions by train category (mean_delay, std_dev) in minutes
    # High-speed trains are generally more punctual but can have larger variance if they hit a major block
    CATEGORY_DISTRIBUTIONS = {
        "VANDE": (5.0, 10.0),    # Vande Bharat: Punctual, tight variance
        "RAJ": (15.0, 20.0),      # Rajdhani: High priority, moderate variance
        "SHT": (10.0, 15.0),      # Shatabdi: Punctual
        "DUR": (20.0, 30.0),      # Duronto
        "SF": (30.0, 45.0),       # Superfast: Standard delay
        "EXP": (45.0, 60.0),      # Express: Higher delay
        "PASS": (60.0, 90.0),     # Passenger: Unreliable
        "DEFAULT": (25.0, 40.0)
    }

    def __init__(self):
        # In a real scenario, this would load from a pre-trained model or Redis
        self._stats_cache: Dict[str, Tuple[float, float]] = {}

    def get_train_distribution(self, train_num: str) -> Tuple[float, float]:
        """Returns (mean_delay_mins, std_dev_mins) for a train."""
        if train_num in self._stats_cache:
            return self._stats_cache[train_num]
            
        # Fallback to category-based estimation
        for cat, dist in self.CATEGORY_DISTRIBUTIONS.items():
            if cat in train_num.upper():
                return dist
        
        return self.CATEGORY_DISTRIBUTIONS["DEFAULT"]

    def calculate_connection_probability(
        self, 
        arr_train_num: str, 
        dep_train_num: str, 
        scheduled_wait_mins: int
    ) -> float:
        """
        Calculates probability of connection success: P(ArrDelay < ScheduledWait + DepDelay)
        Assumes independent normal distributions for delays.
        """
        mu1, sigma1 = self.get_train_distribution(arr_train_num)
        mu2, sigma2 = self.get_train_distribution(dep_train_num)
        
        # Connection fails if: ArrDelay - DepDelay > ScheduledWait
        # Let X = ArrDelay - DepDelay
        # X ~ N(mu1 - mu2, sqrt(sigma1^2 + sigma2^2))
        
        mu_x = mu1 - mu2
        sigma_x = math.sqrt(sigma1**2 + sigma2**2)
        
        if sigma_x == 0:
            return 1.0 if mu_x <= scheduled_wait_mins else 0.0
            
        # z-score for the limit (ScheduledWait)
        z = (scheduled_wait_mins - mu_x) / sigma_x
        
        # Approximation of Normal CDF using error function
        prob = 0.5 * (1 + math.erf(z / math.sqrt(2)))
        
        return max(0.01, min(0.99, prob))

    def get_route_survival_probability(self, probabilities: list[float]) -> float:
        """Combined probability for a multi-transfer route."""
        if not probabilities:
            return 1.0
        
        total_prob = 1.0
        for p in probabilities:
            total_prob *= p
        return total_prob

reliability_engine = ReliabilityEngine()
