import numpy as np

def find_pareto_frontier(costs: np.ndarray) -> np.ndarray:
    """
    Task 16.5: Find the Pareto-optimal points using vectorized comparisons.
    
    A point is Pareto-optimal if no other point is strictly better in at least 
    one dimension AND at least as good in all others.
    
    costs: (N, K) array where N is num points, K is num dimensions.
    Returns boolean mask of shape (N,) where True means the point is on the frontier.
    """
    if costs.shape[0] == 0:
        return np.array([], dtype=bool)
        
    is_efficient = np.ones(costs.shape[0], dtype=bool)
    for i, c in enumerate(costs):
        if is_efficient[i]:
            # Keep only points that are NOT dominated by the current point
            # A point is dominated if it is worse or equal in all dimensions 
            # AND strictly worse in at least one.
            # (In practice, just checking if it's better or equal in ALL is enough
            # to prune redundant or strictly worse points).
            is_efficient[is_efficient] = np.any(costs[is_efficient] < c, axis=1) | \
                                         np.all(costs[is_efficient] == c, axis=1)
            is_efficient[i] = True  # Keep self
            
    return is_efficient
