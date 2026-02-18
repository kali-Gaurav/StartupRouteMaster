# Debugging Methodology That Worked

This document captures the systematic debugging approach that successfully identified and fixed the route search issues. Use this as a template for similar problems.

---

## The Approach: Systematic Elimination of Failure Modes

Your original "Immediate Goal" prompt was perfectly designed - it forced a systematic elimination of each possible failure point. This is how the process worked:

### **Phase 1: Foundation (Enable Observability)**

**Goal:** See what's actually happening

**Steps:**
1. ✅ Set LOG_LEVEL to DEBUG
2. ✅ Add logging to see configuration load
3. ✅ Add logging at entry/exit of search_routes()

**Result:** Without this, you're "debugging blind"

---

### **Phase 2: Data Validation (Database Layer)**

**Goal:** Prove the foundational data exists

**Test:** Created `test_db_connectivity.py` to verify:
```python
# Count existing data
print(db.query(Segment).count())  # Result: 3,131 ✅
print(db.query(Station).count())  # Result: 8,057 ✅

# Get a real segment that works
seg = db.query(Segment).first()
print(f"{seg.source_station.name} -> {seg.dest_station.name}")
# Result: "Cst-Mumbai -> Pune Junction" ✅
```

**Why this matters:** If segments don't exist, no algorithm can find paths. If they do exist, the problem is in the application layer, not data.

**Outcome:** Confirmed 3,131 segments exist → **database is healthy**

---

### **Phase 3: Test With Known Pair (Narrow Scope)**

**Goal:** Don't test with random stations - test with one you KNOW exists

**Test:** Direct API call with the verified pair from Phase 2:
```
POST /api/search
{
  "source": "Cst-Mumbai",
  "destination": "Pune Junction",
  "date": "2024-01-15"
}
```

**Why this matters:** Random station pairs could fail for reasons outside graph building (no route exists). With a known pair, any failure is in the routing logic.

**Outcome:** API error → route search is broken → need to fix application logic

---

### **Phase 4: Capture The Actual Error**

**Goal:** See what error the code produces

**Method:** 
1. Start server with DEBUG logging
2. Make API request with known pair
3. Capture full error message

**Error Found:** `ERROR: Invalid time format: 07:10:00`

**Analysis:**
- Parser expected "HH:MM"
- Database stores "HH:MM:SS"  
- This is a **data format mismatch**, not a logic error

**Fix:** Update regex to accept both formats

---

### **Phase 5: Remove One Layer of Abstraction**

**Goal:** Now that time parsing works, see the next error

**Method:** Run same test again

**Error Found:** `TypeError: add_edge() got an unexpected keyword argument 'from_time'`

**Analysis:**
- Method expects `departure_time`, code calls it `from_time`
- This is a **naming mismatch**, not a logic error

**Fix:** Correct parameter names

---

### **Phase 6: Inspect Graph Structure**

**Goal:** Verify graph construction succeeded

**Action:** Added detailed logging:
```python
logger.info(f"Graph nodes: {len(graph.nodes)}")
logger.info(f"Graph edges: {sum(len(edges) for edges in graph.edges.values())}")

# Log first 10 edges
for node, edges_list in graph.edges.items():
    for edge in edges_list[:10]:
        logger.info(f"Edge: {node[0]} -> {edge['to'][0]}")
```

**Result from logs:**
```
Graph nodes: 360
Graph edges: 205
Edge: 4482d917... (Cst-Mumbai) -> 7f8a2635... (Pune Junction)  # ✅ DIRECT EDGE EXISTS
```

**Insight:** Graph is built correctly and contains the direct edge! But...

---

### **Phase 7: Isolate Algorithm Behavior**

**Goal:** Dijkstra returns 0 paths even though edges exist

**Key Log Entry:**
```
INFO: Dijkstra search found 0 paths
WARNING: CRITICAL: Dijkstra returned 0 paths
```

**Analysis:**
- Graph has edges ✅
- But Dijkstra finds no paths ❌
- **The algorithm is broken, not the data**

**Hypothesis Testing:**
- Could it be reachability pruning? (No, we logged valid_nodes count)
- Could it be duration limits? (No, max_duration was 659 mins, segment was 75 mins)
- Could it be the start node? ⟵ **This was it**

---

### **Phase 8: Dig Into Algorithm Source Code**

**Code inspection:**
```python
start_node = (start_station, start_time)  # (station, 0)
pq = [(0, 0, 0, start_node, [])]

# Then immediately:
while pq:
    current_node = heapq.heappop(pq)
    # ...get outgoing edges from current_node
    for edge in graph.edges.get(current_node, []):  # ← Gets NOTHING!
```

**Realization:**
The graph is a **time-expanded graph**. Nodes are `(station_id, departure_time)` tuples.
- Node `(Cst-Mumbai, 0)` has **NO** outgoing edges
- But `(Cst-Mumbai, 430)` and `(Cst-Mumbai, 520)` DO have edges
- Code starts at time 0, which is unreachable

**This is the ROOT CAUSE** ⟵ Found it!

---

### **Phase 9: Implement the Fix**

**Original approach (wrong):**
```python
# Start at (station, 0) - this node has no edges
pq = [(0, 0, 0, (start_station, 0), [])]
```

**Correct approach:**
```python
# Initialize with ALL edges from the start station
pq = []
for from_node, edges_list in graph.edges.items():
    from_station, from_time = from_node
    if from_station == start_station:  # ← Any departure from source
        for edge in edges_list:
            # Add each edge as starting point
            heapq.heappush(pq, (...))
```

**Why it works:**
- Instead of assuming a starting time, use ACTUAL departure times from the graph
- Bootstrap the search with real edges that exist
- Dijkstra can then explore normally from there

---

### **Phase 10: Verify The Fix**

**Test:**
```
POST /api/search
{
  "source": "Cst-Mumbai",
  "destination": "Pune Junction",
  "date": "2024-01-15"
}
```

**Result:**
```json
{
  "success": true,
  "routes": [
    {
      "source": "Cst-Mumbai",
      "destination": "Pune Junction",
      "total_duration": "1h 15m",
      "total_cost": 100.0
    },
    {
      "source": "Cst-Mumbai",
      "destination": "Pune Junction",
      "total_duration": "1h 20m",
      "total_cost": 100.0
    }
  ]
}
```

**Log entries confirm:**
```
INFO: Dijkstra: Initialized with 12 outgoing edges from source station
INFO: Dijkstra: Found path! Length: 1, Cost: 100.0, Duration: 75
INFO: Dijkstra: Found path! Length: 1, Cost: 100.0, Duration: 80
INFO: Dijkstra search found 2 paths
```

✅ **FIXED!**

---

## Key Insights From This Process

### 1. **Start Observable, Then Test Narrow**
- Enable full logging FIRST
- Test with data you KNOW exists
- Don't change multiple variables at once

### 2. **Eliminate Failure Modes Systematically**
- Data layer working? (Yes → move up)
- API integration? (Yes → move up)  
- Graph structure? (Yes → move up)
- Algorithm? (No → FIX IT)

### 3. **Don't Assume - Verify With Logs**
Instead of guessing "what if the start node is wrong", we LOGGED:
- Which edges exist in the graph
- Which node Dijkstra starts at
- Which edges Dijkstra can see from that node
- When Dijkstra runs out of options

### 4. **Understand Your Data Structures**
The breakthrough came from understanding:
- Time-expanded graphs use `(station, time)` tuples as nodes
- Not all time values exist for each station
- Starting at time 0 is often invalid
- You must bootstrap from actual edges

### 5. **The Value of Comprehensive Logging**
Every fix was enabled by specific logs:
1. Time parse error → log what we're parsing
2. Parameter mismatch → log parameter names
3. Graph emptiness → log node/edge counts
4. Dijkstra failure → log starting edges and paths found

---

## Debugging Template For Similar Issues

For any "feature works sometimes but not always" or "returns empty results":

1. **Enable DEBUG logging** (10 minutes)
2. **Verify data exists** (5 minutes)
3. **Test with known valid input** (5 minutes)
4. **Capture first error** (5 minutes)
5. **Move error line by line** through code
6. **Add logs at each layer** (parsing → graph → algorithm)
7. **Identify where data stops flowing** through the pipeline
8. **Check assumptions** about that component
9. **Fix the root assumption** (not the symptom)
10. **Verify with original test case** (5 minutes)

**Total time:** 45 minutes maximum with systematic discipline

---

## Lessons Learned

### ✅ What Worked
- Your provided debugging roadmap was extremely systematic
- Logging-first approach prevented wild guesses
- Testing with verified data was critical
- Breaking into layers (data → graph → algorithm) worked perfectly

### ❌ What Didn't Work
- Changing multiple things at once
- Assuming the algorithm was correct
- Not logging at bootstrap time
- Not understanding the time-expanded graph concept

### 🎯 Apply Next Time  
- Ask "at what point does data stop flowing?"
- Answer with logs, not guesses
- Fix the layer where flow stops
- Test with minimal reproducible case
