import numpy as np

def find_pareto_frontier(costs: np.ndarray) -> np.ndarray:
    """
    Task 16.5 & 33.2: Find the Pareto-optimal points using vectorized comparisons.
    
    A point is Pareto-optimal if no other point is strictly better in at least 
    one dimension AND at least as good in all others.
    
    costs: (N, K) array where N is num points, K is num dimensions.
    Returns boolean mask of shape (N,) where True means the point is on the frontier.
    """
    n_points = costs.shape[0]
    if n_points == 0:
        return np.array([], dtype=bool)
        
    is_efficient = np.ones(n_points, dtype=bool)
    for i, c in enumerate(costs):
        if is_efficient[i]:
            # Keep only points that are NOT dominated by the current point 'c'
            # A point 'p' is dominated by 'c' if:
            # np.all(c <= p) AND np.any(c < p)
            
            # Optimized vectorized check:
            # We want to keep points that:
            # 1. Are better than 'c' in at least one dimension (np.any(costs < c, axis=1))
            # 2. OR are identical to 'c' (np.all(costs == c, axis=1))
            
            # This logic efficiently prunes points worse than 'c' in all dimensions.
            is_efficient[is_efficient] = np.any(costs[is_efficient] < c, axis=1) | \
                                         np.all(costs[is_efficient] == c, axis=1)
            is_efficient[i] = True  # Always keep the current point being compared
            
    return is_efficient

def normalize_dimensions(data: np.ndarray) -> np.ndarray:
    """
    Task 33.3: Normalize dimensions to 0-1 range for stable Pareto comparisons.
    """
    if data.shape[0] <= 1: return data
    mins = data.min(axis=0)
    maxs = data.max(axis=0)
    ranges = maxs - mins
    # Avoid division by zero
    ranges[ranges == 0] = 1.0
    return (data - mins) / ranges
