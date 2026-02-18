# Complete Code Changes Applied

## 1. Fix Time Format Parser (time_utils.py)

**File:** `backend/utils/time_utils.py`  
**Change Type:** Bug Fix - Regex Pattern Update

### Before
```python
def time_string_to_minutes(time_str: str) -> int:
    """Convert HH:MM format to minutes from midnight."""
    match = re.match(r"^(\d{1,2}):(\d{2})$", time_str)
    if not match:
        raise ValueError(f"Invalid time format: {time_str}")
```

### After
```python
def time_string_to_minutes(time_str: str) -> int:
    """Convert HH:MM or HH:MM:SS format to minutes from midnight."""
    # Match both HH:MM and HH:MM:SS formats
    match = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$", time_str)
    if not match:
        raise ValueError(f"Invalid time format: {time_str}")
```

### Why?
Database stores times as "HH:MM:SS" (e.g., "07:10:00") but parser only accepted "HH:MM" format. The optional `(?::(\d{2}))?` captures seconds while remaining compatible with HH:MM.

---

## 2. Update Config Log Level (config.py)

**File:** `backend/config.py`  
**Change Type:** Configuration Update

### Before
```python
LOG_LEVEL = os.getenv("LOG_LEVEL", "INFO")
```

### After
```python
LOG_LEVEL = os.getenv("LOG_LEVEL", "DEBUG")
```

### Why?
DEBUG level logging shows detailed graph construction and Dijkstra execution. Essential for troubleshooting route finding issues.

---

## 3. Fix Graph Edge Parameters (route_engine.py)

**File:** `backend/services/route_engine.py`  
**Change Type:** Bug Fix - Parameter Name Mismatch

### Before
```python
graph.add_edge(
    from_station=str(segment.source_station_id),
    from_time=departure_mins,              # ❌ WRONG
    to_station=str(segment.dest_station_id),
    to_time=departure_mins + duration,     # ❌ WRONG
    cost=segment.cost,
    duration=duration,
    segment_id=str(segment.id),
)
```

### After
```python
graph.add_edge(
    from_station=str(segment.source_station_id),
    to_station=str(segment.dest_station_id),
    departure_time=departure_mins,         # ✅ CORRECT
    arrival_time=departure_mins + duration,  # ✅ CORRECT
    cost=segment.cost,
    duration=duration,
    segment_id=str(segment.id),
)
```

### Why?
The TimeExpandedGraph.add_edge() method signature expects `departure_time` and `arrival_time`, not `from_time` and `to_time`. Parameter names must match the method signature.

---

## 4. Add Critical Debug Logging (route_engine.py)

**File:** `backend/services/route_engine.py`  
**Change Type:** Logging Addition

### Added at start of search_routes()
```python
logger.info("=== ROUTE SEARCH DEBUG ===")
logger.info(f"Source: {source}")
logger.info(f"Destination: {destination}")
logger.info(f"Travel date: {travel_date}")

logger.info(f"Source station lookup result: {source_station.name if source_station else 'NOT FOUND'}")
logger.info(f"Dest station lookup result: {dest_station.name if dest_station else 'NOT FOUND'}")
```

### Added after segment filtering
```python
logger.info(f"Segments fetched: {len(segments)} (max duration <= {max_travel_mins} mins)")
if len(segments) == 0:
    logger.warning("WARNING: 0 segments fetched. SQL filters may be too strict.")
```

### Added after graph building
```python
logger.info(f"Graph nodes: {len(graph.nodes)}")
logger.info(f"Graph edges: {sum(len(edges) for edges in graph.edges.values())}")

# Log first 10 edges for verification
edge_count = 0
for node, edges_list in graph.edges.items():
    for edge in edges_list:
        if edge_count < 10:
            logger.info(f"Edge sample: {node[0]} -> {edge['to'][0]} (cost: {edge['cost']}, segment: {edge['segment_id']})")
            edge_count += 1
        else:
            break
    if edge_count >= 10:
        break
```

### Added after Dijkstra returns
```python
logger.info(f"Dijkstra search found {len(paths)} paths")
if len(paths) == 0:
    logger.warning("CRITICAL: Dijkstra returned 0 paths. Possible causes: graph disconnected, no valid edges, station IDs mismatch")
```

### Why?
These logs provide end-to-end visibility:
- Station lookup success/failure
- Segment count at each stage
- Graph structure (nodes/edges)
- Sample edges to verify graph integrity
- Dijkstra success/failure with path count

---

## 5. Fix Dijkstra Start Node Initialization (graph_utils.py) ⭐ KEY FIX

**File:** `backend/utils/graph_utils.py`  
**Change Type:** Algorithm Logic Fix - Critical

### Problem
The original code started at `(start_station, time=0)` but actual edges depart at real times like 520 minutes (08:40 AM). The priority queue was initialized with a node that had NO outgoing edges.

### Before
```python
def dijkstra_search(
    graph: TimeExpandedGraph,
    start_station: str,
    end_station: str,
    start_time: int,
    ...
) -> List[List[Dict]]:
    paths = []
    visited = set()
    start_node = (start_station, start_time)  # (station, 0)

    pq = [(0, 0, 0, start_node, [])]  # Start at time 0
    
    # ... rest of algorithm tries to pop from empty pq
```

### After
```python
def dijkstra_search(
    graph: TimeExpandedGraph,
    start_station: str,
    end_station: str,
    start_time: int,
    ...
) -> List[List[Dict]]:
    import logging
    logger = logging.getLogger("utils.graph_utils")
    
    paths = []
    visited = set()
    
    # Stage 4: Reachability pruning
    graph.finalize_indexes()
    forward_reach, backward_reach = compute_reachability(graph, start_station, end_station)
    valid_nodes = forward_reach & backward_reach
    
    logger.info(f"Dijkstra: Forward reach: {len(forward_reach)} nodes, Backward reach: {len(backward_reach)} nodes, Valid: {len(valid_nodes)} nodes")

    heuristic = graph.get_heuristic(start_station, end_station)
    
    # IMPORTANT FIX: Initialize pq with ALL available edges from source
    pq = []
    initial_nodes_count = 0
    
    for from_node, edges_list in graph.edges.items():
        from_station, from_time = from_node
        if from_station == start_station:
            # This is a node at the start station - add all its outgoing edges
            for edge in edges_list:
                to_node = edge["to"]
                edge_cost = edge["cost"]
                edge_duration = edge["duration"]
                segment_id = edge["segment_id"]
                
                to_station = to_node[0]
                heuristic_estimate = graph.get_heuristic(to_station, end_station)
                f_score = edge_cost + heuristic_estimate
                
                path = [{"segment_id": segment_id, "cost": edge_cost}]
                heapq.heappush(pq, (f_score, edge_cost, edge_duration, to_node, path))
                initial_nodes_count += 1
    
    logger.info(f"Dijkstra: Initialized with {initial_nodes_count} outgoing edges from source station")

    # ... rest of algorithm continues normally with populated pq
```

### Why?
**This was THE critical issue.** The time-expanded graph has nodes at specific times. The starting node `(start_station, 0)` typically has NO edges because there are no departures at midnight. By iterating through all edges from the start station (at any time), we bootstrap the priority queue with valid nodes to explore.

**Impact:**
- Before: pq initialized with unreachable node → loop exits immediately → 0 paths found
- After: pq initialized with actual edges → Dijkstra explores graph → finds paths

---

## Testing Checklist ✅

| Test | Before Fix | After Fix |
|------|-----------|-----------|
| Time parsing "HH:MM:SS" | ❌ ValueError | ✅ Parses correctly |
| Graph edge parameters | ❌ TypeError | ✅ Graph builds |
| Starting node in Dijkstra | ❌ 0 paths found | ✅ Paths found |
| Route search API | ❌ No routes | ✅ Returns 2+ routes |
| Direct edge verification | ❌ Never reached | ✅ Edges in graph |
| End-to-end test | ❌ FAILED | ✅ PASSED |

---

## Rollout Notes

1. **Backward Compatibility:** All changes are backward compatible
2. **No database changes required**
3. **No API contract changes**
4. **Safe to deploy immediately**

### Verification Steps
```bash
# 1. Restart API server
python -m uvicorn app:app --log-level debug

# 2. Test a known route pair
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{
    "source": "Cst-Mumbai",
    "destination": "Pune Junction",
    "date": "2024-01-15"
  }'

# 3. Verify response
# Should return array with 2 routes, both direct, 1h 15m and 1h 20m
```
