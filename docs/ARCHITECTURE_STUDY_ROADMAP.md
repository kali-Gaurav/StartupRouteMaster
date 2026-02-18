# Architecture Study Roadmap 🗺️

## Understanding Your System in 3 Levels

---

## Level 1: Quick Reference (5 min) ⚡

### Your System Has 2 Databases

```
┌─────────────────────────────┐
│   SQLITE (Local File)       │
│  railway_manager.db         │
│  Contains: Trains, schedules │
│  Rows: ~40,000 train legs   │
│  Problem: NOT synced!       │
└────────┬────────────────────┘
         │
         │ ❌ MISSING BRIDGE
         │
┌────────▼────────────────────┐
│  POSTGRESQL (Supabase Cloud)│
│  Contains: Bookings, routes │
│  Rows: 0 in segments table  │
│  Problem: EMPTY!            │
└─────────────────────────────┘
```

### The 3 Tables Explained

| Table | DB | Stores | Example |
|-------|----|----|---------|
| `train_routes` | SQLite | Train paths A→B→C | NDLS→ALD→KOTA |
| `segments` | PostgreSQL | Bookable legs with times | NDLS→ALD, 08:00-11:30, ₹450 |
| `routes` | PostgreSQL | Multi-leg journeys (search results) | [Segment1 + Segment2], total ₹1100 |

### Why Search Fails

1. User searches: "Delhi → Mumbai"
2. RouteEngine queries `segments` table
3. Segments table is **EMPTY** 🔴
4. No trains found
5. Returns [] to user

### The Fix

1. Read from SQLite `train_schedule`
2. Write to PostgreSQL `segments`
3. **One ETL script = system works** ✅

---

## Level 2: Deep Understanding (30 min) 📚

### Read These Files (In Order)

1. **ARCHITECTURE_STUDY_SUMMARY.md** ← YOU ARE HERE
   - 3-table comparison
   - Data relationships
   - Why segments is empty

2. **DATABASE_ARCHITECTURE_DEEP_DIVE.md**
   - Complete schema definitions
   - Data flow diagrams
   - Architecture issues explained

3. **DATABASE_ARCHITECTURE_DIAGRAMS.md**
   - Visual mermaid diagrams
   - Transformation examples
   - Code flow charts

### Key Concepts

- **SQLite** = Master data source (external provider)
- **PostgreSQL** = Application database (your product)
- **ETL** = Extract-Transform-Load (missing bridge)
- **Segments** = Individual train legs (should have 40,000+)
- **Routes** = Multi-leg journeys (computed from segments)

---

## Level 3: Implementation (1-2 hours) 🔧

### Read This File

**ETL_IMPLEMENTATION_GUIDE.md** - Full working code

### What to Build

```
File: backend/etl/sqlite_to_postgres.py
Purpose: Read SQLite, write PostgreSQL
Result: Populate segments table (40,000 rows)
Time: ~1 hour to code
```

### Steps

1. **Create ETL script** (copy template from Implementation Guide)
2. **Test locally** (verify segments table populated)
3. **Verify search works** (RouteEngine finds trains)
4. **Deploy** (run daily via Cloud Scheduler)

---

## Study Guide by Role

### If You're a **Backend Developer**

**Goal**: Understand the database architecture and build the ETL

**Read**:
1. ARCHITECTURE_STUDY_SUMMARY.md (schema comparison)
2. DATABASE_ARCHITECTURE_DEEP_DIVE.md (full details)
3. ETL_IMPLEMENTATION_GUIDE.md (code template)

**Build**:
1. Copy `sqlite_to_postgres.py` template
2. Add to your project: `backend/etl/`
3. Run & test locally
4. Deploy with Cloud Scheduler

**Time**: 2-3 hours total

---

### If You're a **DevOps Engineer**

**Goal**: Set up ETL pipeline & automation

**Read**:
1. ARCHITECTURE_STUDY_SUMMARY.md (quick overview)
2. ETL_IMPLEMENTATION_GUIDE.md (deployment section)
3. DATABASE_ARCHITECTURE_DIAGRAMS.md (data flow)

**Set up**:
1. Create `backend/etl/` directory structure
2. Deploy ETL script to production
3. Configure Cloud Scheduler for daily runs
4. Set up alerting for failures
5. Monitor execution logs

**Time**: 1-2 hours setup + ongoing monitoring

---

### If You're a **Product Manager**

**Goal**: Understand why search doesn't work & what's needed

**Read**:
1. ARCHITECTURE_STUDY_SUMMARY.md (start here! 5 min)
2. "The Critical Gap ❌" section (explains the problem)
3. "Why Search Fails" (the user-facing impact)

**Outcome**:
- Understand: Segments table is empty
- Know: One ETL script fixes everything
- Decide: Whether to prioritize this

**Time**: 15 minutes

---

### If You're a **QA/Tester**

**Goal**: Know what to test & what should work

**Read**:
1. ARCHITECTURE_STUDY_SUMMARY.md (understand the 3 tables)
2. "What Happens When User Searches" (test flow)
3. ETL_IMPLEMENTATION_GUIDE.md (test suite section)

**Test**:
1. Before ETL: segments table is empty, search returns []
2. After ETL: segments has 40,000+ rows, search returns results
3. Run test suite: `pytest backend/etl/tests/test_etl.py`

**Time**: 30 minutes testing + ongoing validation

---

## Checklist

### Understanding Phase
- [ ] Read ARCHITECTURE_STUDY_SUMMARY.md (you are here)
- [ ] Read DATABASE_ARCHITECTURE_DEEP_DIVE.md
- [ ] Read DATABASE_ARCHITECTURE_DIAGRAMS.md
- [ ] Understand why segments table is empty
- [ ] Understand the 3 tables (train_routes, segments, routes)

### Implementation Phase
- [ ] Create `backend/etl/` directory
- [ ] Copy sqlite_to_postgres.py template
- [ ] Update railway_manager.db path (if different)
- [ ] Update DATABASE_URL in config
- [ ] Run locally: `python -m backend.etl.sqlite_to_postgres`
- [ ] Verify: `SELECT COUNT(*) FROM segments;` → should be 40,000+
- [ ] Test: RouteEngine search works

### Deployment Phase
- [ ] Push code to git
- [ ] Deploy to production
- [ ] Add `/api/admin/etl-sync` endpoint
- [ ] Configure Cloud Scheduler
- [ ] Set up alerting
- [ ] Document in team wiki
- [ ] Mark as complete in project tracker

---

## What Each File Covers

### ARCHITECTURE_STUDY_SUMMARY.md
**Focus**: High-level overview & quick reference

**Topics**:
- The 3 tables compared
- Why search fails
- The critical gap
- Action items by role

**Read if**: You want the 5-minute version

---

### DATABASE_ARCHITECTURE_DEEP_DIVE.md
**Focus**: Complete technical details & schema documentation

**Topics**:
- SQLite schema with examples
- PostgreSQL schema definition
- Data relationships (ER model)
- How routes are produced
- Current code flow
- Design recommendations

**Read if**: You want all the details

---

### DATABASE_ARCHITECTURE_DIAGRAMS.md
**Focus**: Visual representations & transformation flows

**Topics**:
- Mermaid diagrams (system architecture, data flow, relationships)
- SQLite-to-PostgreSQL transformation
- Example: How a route is created
- The critical problem illustrated visually

**Read if**: You're a visual learner

---

### ETL_IMPLEMENTATION_GUIDE.md
**Focus**: Practical implementation with working code

**Topics**:
- Step-by-step transformation logic
- Full Python code (copy-paste ready)
- Test suite
- Deployment options
- Cloud Scheduler setup

**Read if**: You need to build/deploy the ETL

---

## Time Investment vs. Understanding

```
15 minutes → ARCHITECTURE_STUDY_SUMMARY.md
  = You know what's broken

30 minutes → + DATABASE_ARCHITECTURE_DEEP_DIVE.md
  = You understand why it's broken

45 minutes → + DATABASE_ARCHITECTURE_DIAGRAMS.md
  = You can visualize the fix

2+ hours → + ETL_IMPLEMENTATION_GUIDE.md + Code
  = You can build the fix
```

---

## Testing Your Understanding

### Question 1: What's the difference between `train_routes` and `segments`?

**Good Answer**:
- `train_routes` (SQLite): Defines which trains go which direction (static definition)
- `segments` (PostgreSQL): Specific train services with times and prices (should be 40,000+ rows)

### Question 2: Why can't users find trains?

**Good Answer**:
- The segments table is empty because there's no ETL script to populate it from SQLite
- RouteEngine queries an empty segments table, finds no trains, returns no results

### Question 3: What does the missing ETL script do?

**Good Answer**:
- Reads: SQLite train_schedule + train_routes + train_fares tables
- Transforms: Joins them and calculates duration, cost, operating days
- Loads: Creates Segment rows in PostgreSQL segments table

---

## The 3 Key Insights

### Insight 1: Two Completely Separate Systems
You don't have one database. You have two databases doing different things. SQLite is a data warehouse. PostgreSQL is the app database. They need to be connected.

### Insight 2: The Segments Table is the Bridge
The `segments` table in PostgreSQL should mirror the train services from SQLite. Right now it's empty, so nothing works.

### Insight 3: One Script Fixes Everything
Build one ETL script, run it once, and 40,000 train services appear in PostgreSQL. Your app immediately starts working.

---

## Common Questions

### Q: Why is there a railway_manager.db file in my repo?
**A**: It's a local copy of the master data. `copy_tables.py` keeps it in sync with `railway_manager01.db`.

### Q: Why use SQLite for master data?
**A**: Probably downloaded from external provider, stored locally for performance, or legacy system integration.

### Q: Why not just use SQLite for the app?
**A**: PostgreSQL is better for cloud deployments (Supabase). SQLite is for local data only.

### Q: How do I know segments table should have 40,000 rows?
**A**: Indian railway has ~8,000 stations and ~1,000+ trains. Each train goes through multiple stations = many segments.

### Q: Will this slow down the app?
**A**: This doesn't slow anything down. ETL happens once/daily in the background. App queries are fast because data is indexed.

---

## Next Actions

### For Developers
```bash
# 1. Read the docs (30 min)
# 2. Implement ETL (1 hour)
# 3. Test locally (30 min)
# 4. Deploy (30 min)
# Total: ~2.5 hours
```

### For DevOps
```bash
# 1. Review ETL script (20 min)
# 2. Deploy to prod (30 min)
# 3. Set up scheduler (30 min)
# 4. Verify & monitor (20 min)
# Total: ~2 hours
```

### For Management
```
Decision: Approve 2-3 hours engineering time
Impact: App search functionality = enabled
ROI: Enables core feature, prevents customer issues
```

---

## Success Metrics

After implementing ETL:

✅ `SELECT COUNT(*) FROM segments;` → 40,000+ (not 0)
✅ User searches → Returns 3-5 route options (not "no results")
✅ RouteEngine uses real train data (not test data)
✅ Bookings reference real segments (not dummy entries)
✅ Daily scheduler runs ETL (keeps data fresh)

---

## Documentation Map

```
YOU ARE HERE ↓
┌─────────────────────────────────────────┐
│  ARCHITECTURE_STUDY_SUMMARY.md          │  Quick reference
│  (This file - you're reading it!)       │
└──────────┬──────────────────────────────┘
           │
           ├── Need more detail?
           │   └→ DATABASE_ARCHITECTURE_DEEP_DIVE.md
           │
           ├── Visual learner?
           │   └→ DATABASE_ARCHITECTURE_DIAGRAMS.md
           │
           └── Ready to code?
               └→ ETL_IMPLEMENTATION_GUIDE.md
```

---

## Final Word

You've identified a **critical gap** in your architecture. The good news: **it's a simple fix**. One ETL script bridges the gap. Your system will immediately start working. This should be your next priority.

Good luck! 🚀

---

## Quick Links

- Read next: [DATABASE_ARCHITECTURE_DEEP_DIVE.md](./DATABASE_ARCHITECTURE_DEEP_DIVE.md)
- Diagrams: [DATABASE_ARCHITECTURE_DIAGRAMS.md](./DATABASE_ARCHITECTURE_DIAGRAMS.md)
- Code: [ETL_IMPLEMENTATION_GUIDE.md](./ETL_IMPLEMENTATION_GUIDE.md)
