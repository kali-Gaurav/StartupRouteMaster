import logging
import re
from typing import Any

logger = logging.getLogger("query-analyzer")

class QueryCostAnalyzer:
    """
    Subtask 4.8: Query Cost Analyzer & Shedder.
    Analyzes SQL statements before execution to prevent resource exhaustion.
    """
    def __init__(self):
        # Heavy keywords that indicate a complex query
        self.heavy_keywords = ["JOIN", "GROUP BY", "UNION", "DISTINCT"]
        self.is_degraded = False # Toggled by jit_manager

    def estimate_cost(self, statement: Any) -> int:
        """
        Returns a simplified 'cost' score based on SQL string analysis.
        """
        sql = str(statement).upper()
        cost = 1 # Base cost
        
        # 1. Join Penalty
        joins = sql.count("JOIN")
        cost += (joins * 5)
        
        # 2. Aggregation Penalty
        if "GROUP BY" in sql: cost += 3
        if "DISTINCT" in sql: cost += 2
        
        # 3. Subquery Penalty
        subqueries = sql.count("SELECT") - 1
        cost += (subqueries * 4)
        
        return cost

    def should_shed(self, statement: Any, current_jit_state: str) -> bool:
        """
        Decides if a query should be dropped based on system state.
        """
        cost = self.estimate_cost(statement)
        
        # If JIT is degraded, we reject any query with cost > 5
        if current_jit_state == "degraded" and cost > 5:
            logger.warning(f"🚫 Query Shedding: Dropping heavy query (Cost: {cost}) during degraded state.")
            return True
            
        # Hard limit for any state
        if cost > 25:
            logger.error(f"🚨 Query Shedding: Dropping extreme query (Cost: {cost}) to prevent crash.")
            return True
            
        return False

query_analyzer = QueryCostAnalyzer()
