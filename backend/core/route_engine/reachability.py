import numpy as np
import logging
from typing import Dict, List, Set, Optional
from datetime import datetime
import os

logger = logging.getLogger(__name__)

class ClusterReachabilityMatrix:
    """
    [Task 146.1] High-Performance City Cluster Reachability Matrix.
    Stores bitsets indicating which clusters are reachable from each other on a specific date.
    Size: ~500 clusters, 31KB per date. Extremely fast L2-cache friendly lookups.
    """
    def __init__(self, date: datetime, cluster_to_idx: Dict[str, int]):
        self.date = date
        self.date_str = date.strftime("%Y%m%d")
        self.cluster_to_idx = cluster_to_idx
        self.idx_to_cluster = {v: k for k, v in cluster_to_idx.items()}
        self.num_clusters = len(cluster_to_idx)
        
        # Matrix: [Source Cluster Index] -> [Bitset of reachable Cluster Indices]
        # We use a bitset (represented as uint64 words) for each source cluster.
        self.words_per_row = (self.num_clusters // 64) + 1
        self.matrix = np.zeros((self.num_clusters, self.words_per_row), dtype=np.uint64)

    def set_reachable(self, src_cluster: str, dst_cluster: str):
        """Mark dst reachable from src on this date."""
        s_idx = self.cluster_to_idx.get(src_cluster)
        d_idx = self.cluster_to_idx.get(dst_cluster)
        
        if s_idx is not None and d_idx is not None:
            self.matrix[s_idx, d_idx // 64] |= (np.uint64(1) << np.uint64(d_idx % 64))

    def compute_transitive_closure(self):
        """
        [Task 146.3] Multi-hop search triage.
        Propagates reachability so that if A->B and B->C, then A->C.
        Uses bitwise row propagation.
        """
        logger.info(f"🔄 Computing Transitive Closure for {self.num_clusters} clusters...")
        changed = True
        iterations = 0
        while changed and iterations < 5: # Limit depth for performance/sanity
            changed = False
            iterations += 1
            for i in range(self.num_clusters):
                old_row = self.matrix[i].copy()
                # Find all clusters visited from 'i'
                # For each visited cluster 'j', OR row 'i' with row 'j'
                for j in range(self.num_clusters):
                    if (self.matrix[i, j // 64] & (np.uint64(1) << np.uint64(j % 64))):
                        self.matrix[i] |= self.matrix[j]
                
                if not np.array_equal(old_row, self.matrix[i]):
                    changed = True
        logger.info(f"✅ Closure complete in {iterations} iterations.")

    def is_reachable(self, src_cluster: str, dst_cluster: str) -> bool:
        """[Task 146.5 Gatekeeper] O(1) Check if destination cluster is reachable from source."""
        s_idx = self.cluster_to_idx.get(src_cluster)
        d_idx = self.cluster_to_idx.get(dst_cluster)
        
        if s_idx is None or d_idx is None:
            return True # Conservative default: if unknown, allow search
            
        return bool(self.matrix[s_idx, d_idx // 64] & (np.uint64(1) << np.uint64(d_idx % 64)))

    def save(self, directory: str):
        """Save to disk for MemMap/Instant Load."""
        if not os.path.exists(directory): os.makedirs(directory)
        filename = os.path.join(directory, f"reach_cluster_{self.date_str}.npy")
        np.save(filename, self.matrix)
        # Store index mapping separately
        import json
        with open(os.path.join(directory, f"reach_cluster_{self.date_str}_idx.json"), 'w') as f:
            json.dump(self.cluster_to_idx, f)

    @classmethod
    def load(cls, date: datetime, directory: str) -> Optional['ClusterReachabilityMatrix']:
        """[Subtask 146.4] Instant load cluster matrix using MemMap."""
        date_str = date.strftime("%Y%m%d")
        idx_file = os.path.join(directory, f"reach_cluster_{date_str}_idx.json")
        matrix_file = os.path.join(directory, f"reach_cluster_{date_str}.npy")
        
        if not (os.path.exists(idx_file) and os.path.exists(matrix_file)):
            return None
            
        try:
            import json
            with open(idx_file, 'r') as f:
                cluster_to_idx = json.load(f)
            
            instance = cls(date, cluster_to_idx)
            # Use mmap_mode='r' for zero-copy read-only disk access
            instance.matrix = np.load(matrix_file, mmap_mode='r')
            return instance
        except Exception as e:
            logger.error(f"Failed to load reachability matrix: {e}")
            return None
