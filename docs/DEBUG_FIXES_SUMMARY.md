# Route Search Debugging & Fixes - Summary

**Date:** February 12, 2026  
**Status:** ✅ **RESOLVED** - Route search now working successfully

---

## Problem Statement

The railway route search API was returning **0 routes** even when:
- ✅ Database had 3,131 valid segments
- ✅ Graph was correctly built with 360 nodes and 205 edges  
- ✅ Direct connections existed (e.g., **Cst-Mumbai → Pune Junction** with cost 100)
- ❌ But Dijkstra's algorithm returned **0 paths**

---

## Root Cause Analysis

### Three Critical Issues Were Found & Fixed

#### **Issue #1: Time Format Parsing Error** 
**Symptom:** `ValueError: Invalid time format: 07:10:00`

**Root Cause:** The `time_string_to_minutes()` function expected "HH:MM" format, but the database stores times as "HH:MM:SS".

**Fix Applied:**
```python
# File: backend/utils/time_utils.py

# BEFORE (rejected HH:MM:SS):
match = re.match(r"^(\d{1,2}):(\d{2})$", time_str)

# AFTER (accepts both HH:MM and HH:MM:SS):
match = re.match(r"^(\d{1,2}):(\d{2})(?::(\d{2}))?$", time_str)
```

**Impact:** Without this fix, route engine crashed with parsing error before graph was even built.

---

#### **Issue #2: Incorrect Graph Edge Parameters**
**Symptom:** `TypeError: add_edge() got an unexpected keyword argument 'from_time'`

**Root Cause:** The method signature expected `departure_time` and `arrival_time`, but was being called with `from_time` and `to_time`.

**Fix Applied:**
```python
# File: backend/services/route_engine.py

# BEFORE:
graph.add_edge(
    from_station=..., 
    from_time=departure_mins,        # ❌ WRONG
    to_station=..., 
    to_time=departure_mins + duration # ❌ WRONG
)

# AFTER:
graph.add_edge(
    from_station=..., 
    to_station=..., 
    departure_time=departure_mins,    # ✅ CORRECT
    arrival_time=departure_mins + duration  # ✅ CORRECT
)
```

**Impact:** Graph construction would fail silently or throw exception.

---

#### **Issue #3: Dijkstra Start Node Initialization** ⭐ **KEY FIX**
**Symptom:** Dijkstra returned **0 paths** despite valid edges existing in graph

**Root Cause:** The algorithm started at `(start_station, time=0)`, but actual edges from Cst-Mumbai depart at times like **520 mins (8:40 AM)**, not 0. The priority queue had no outgoing edges from the starting node.

**Fix Applied:**
```python
# File: backend/utils/graph_utils.py

# BEFORE: Started at fixed time 0 with no outgoing edges
start_node = (start_station, start_time)
pq = [(0, 0, 0, start_node, [])]
# Result: No edges from (start_station, 0) → pq becomes empty → 0 paths

# AFTER: Initialize priority queue with ALL available edges from source
pq = []
for from_node, edges_list in graph.edges.items():
    from_station, from_time = from_node
    if from_station == start_station:
        # Add each edge as a starting candidate
        for edge in edges_list:
            heapq.heappush(pq, (...edge_cost..., to_node, [segment]))

# Result: pq has valid edges to explore → Dijkstra finds paths successfully
```

**Impact:** **This was the critical blocker** preventing any paths from being found.

---

## Verification Results

### Database Verification ✅
```
Database:
- Segments: 3,131
- Stations: 8,057
- Verified pair: Cst-Mumbai → Pune Junction exists
```

### Graph Construction ✅
```
Graph stats:
- Nodes: 360
- Edges: 205
- Direct edge sample: 
  Cst-Mumbai → Pune Junction (cost: 100.0)
```

### Route Search After Fixes ✅
```
API Test: Cst-Mumbai → Pune Junction (2024-01-15)

Response:
✅ Route 1: 1h 15m, Cost: ₹100 (direct)
✅ Route 2: 1h 20m, Cost: ₹100 (direct)
✅ Dijkstra found 2 paths
✅ API returned 2 routes
```

---

## Code Changes Summary

| File | Changes | Purpose |
|------|---------|---------|
| `config.py` | `LOG_LEVEL: INFO → DEBUG` | Enable debug logging to see graph construction |
| `utils/time_utils.py` | Regex: `(\d{2})$` → `(\d{2})(?::(\d{2}))?$` | Accept HH:MM:SS format |
| `services/route_engine.py` | Fixed parameter names: `from_time` → `departure_time` | Match method signature |
| `services/route_engine.py` | Added critical debug logs | Log node/edge counts and first 10 edges |
| `utils/graph_utils.py` | **Reimplemented dijkstra_search()** | Initialize with actual source edges instead of (station, 0) |

---

## Lessons & Best Practices

### What Went Wrong
1. **Time format mismatch** - ETL data format didn't match parser expectations
2. **Parameter name mismatch** - Documentation vs. actual code divergence
3. **Graph initialization bug** - Algorithm assumed start_time=0 was valid, but ignored actual edge departure times

### How to Prevent
- ✅ Add unit tests for time parsing with multiple formats
- ✅ Validate ETL output schema matches code expectations  
- ✅ Add comprehensive logging at algorithm entry points
- ✅ Debug print-statement approach: Verify assumptions with concrete logging

---

## Testing Recommendations

### Unit Tests Needed
- `test_time_utils.py`: Test time parsing with HH:MM, HH:MM:SS, and invalid formats
- `test_graph_builder.py`: Verify graph construction from segments
- `test_dijkstra.py`: Direct dijkstra calls with minimal graphs

### Integration Test
```bash
curl -X POST http://localhost:8000/api/search \
  -H "Content-Type: application/json" \
  -d '{"source":"Cst-Mumbai","destination":"Pune Junction","date":"2024-01-15"}'
```

Expected: **200 OK** with array of 1+ routes

---

## Files Modified
- ✅ `backend/config.py`
- ✅ `backend/utils/time_utils.py`  
- ✅ `backend/services/route_engine.py`
- ✅ `backend/utils/graph_utils.py`

**All changes tested and verified working**
