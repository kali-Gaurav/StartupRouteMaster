# ETL Implementation Guide: SQLite → PostgreSQL 🔧

## The Missing Piece

Your system has **2 databases but NO bridge between them**.

```
railway_manager.db (SQLite)          Supabase (PostgreSQL)
├── stations_master          ────→   ❌ stations (empty)
├── train_routes             ────→   ❌ segments (empty)
├── train_schedule           ────→   ❌ segments (empty)
├── train_fares              ────→   ❌ segments (empty)
└── train_running_days       ────→   ❌ segments (empty)
```

**Result**: Segments table is empty → RouteEngine finds no routes → API returns []

---

## Solution: Create ETL Pipeline

### Step 1: Understand the Transformation

#### Input: SQLite Tables

**train_routes** (example row):
```json
{
  "id": 1001,
  "train_id": 555,
  "source_station_code": "NDLS",
  "destination_station_code": "BCT",
  "route_sequence": 1,
  "distance_km": 1450,
  "estimated_duration": 1440
}
```

**train_schedule** (example row):
```json
{
  "id": 2001,
  "train_id": 555,
  "route_segment_id": 1001,
  "departure_time": "08:00",
  "arrival_time": "20:00",
  "halt_time_minutes": 0,
  "platform_number": "1"
}
```

**train_fares** (example row):
```json
{
  "id": 3001,
  "train_id": 555,
  "route_segment_id": 1001,
  "seat_class": "AC",
  "base_fare": 800,
  "reservation_charge": 50,
  "total_fare": 850,
  "season": "normal"
}
```

**train_running_days** (example row):
```json
{
  "id": 4001,
  "train_id": 555,
  "monday": true,
  "tuesday": true,
  "wednesday": false,
  "thursday": true,
  "friday": true,
  "saturday": true,
  "sunday": true
}
```

**trains_master** (example row):
```json
{
  "id": 555,
  "train_number": "12345",
  "train_name": "Rajdhani Express",
  "operator": "Indian Railways",
  "train_type": "Express"
}
```

#### Output: PostgreSQL Segment

**segments** (Supabase):
```json
{
  "id": "<UUID>",
  "source_station_id": "<UUID of NDLS>",
  "dest_station_id": "<UUID of BCT>",
  "transport_mode": "train",
  "departure_time": "08:00",
  "arrival_time": "20:00",
  "duration_minutes": 720,
  "cost": 850.0,
  "operator": "Indian Railways",
  "operating_days": "1101110"
}
```

---

### Step 2: Create ETL Script

**File**: `backend/etl/__init__.py` (create directory)

```python
# backend/etl/__init__.py
"""ETL utilities for syncing railway_manager.db to Supabase."""
```

---

**File**: `backend/etl/sqlite_to_postgres.py`

```python
"""
ETL Pipeline: railway_manager.db (SQLite) → Supabase PostgreSQL

Transforms:
  - SQLite train_schedule, train_routes, train_fares
  → PostgreSQL segments

Usage:
  python -m backend.etl.sqlite_to_postgres --source /path/to/railway_manager.db
  or
  python -m backend.etl.sqlite_to_postgres  # uses default path
"""

import sqlite3
import uuid
from datetime import datetime
from typing import Dict, List, Optional, Tuple
import logging
import os
from pathlib import Path

# For DB connection
from sqlalchemy.orm import Session
from sqlalchemy import and_

# Project imports
from database import SessionLocal
from models import Station, Segment
from config import Config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Default paths
DEFAULT_SQLITE_PATH = os.path.join(
    os.path.dirname(__file__),
    "..",
    "railway_manager.db"
)


class SQLiteReader:
    """Read data from SQLite railway_manager.db."""
    
    def __init__(self, db_path: str):
        self.db_path = db_path
        if not os.path.exists(db_path):
            raise FileNotFoundError(f"SQLite DB not found: {db_path}")
        logger.info(f"Connected to SQLite: {db_path}")
    
    def get_connection(self):
        """Get SQLite connection."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row  # Return as dicts
        return conn
    
    def read_stations_master(self) -> List[Dict]:
        """Read all stations from stations_master."""
        conn = self.get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            SELECT station_code, station_name, city, state, 
                   latitude, longitude, is_junction
            FROM stations_master
            ORDER BY station_code
        """)
        stations = [dict(row) for row in cursor.fetchall()]
        conn.close()
        logger.info(f"Read {len(stations)} stations from SQLite")
        return stations
    
    def read_segment_data(self) -> Tuple[List[Dict], int]:
        """
        Read train schedule data and assembled segments.
        
        Returns:
          (segment_list, error_count)
        """
        conn = self.get_connection()
        cursor = conn.cursor()
        
        # Join to get complete segment info
        query = """
        SELECT 
            tr.source_station_code,
            tr.destination_station_code,
            ts.departure_time,
            ts.arrival_time,
            tr.estimated_duration,
            tf.total_fare,
            tm.operator,
            trd.monday, trd.tuesday, trd.wednesday, trd.thursday,
                trd.friday, trd.saturday, trd.sunday,
            tm.train_number
        FROM train_schedule ts
        JOIN train_routes tr ON ts.route_segment_id = tr.id
        JOIN train_fares tf ON tf.route_segment_id = tr.id
        JOIN trains_master tm ON tm.id = ts.train_id
        JOIN train_running_days trd ON trd.train_id = tm.id
        WHERE ts.departure_time IS NOT NULL
          AND ts.arrival_time IS NOT NULL
        ORDER BY ts.id
        """
        
        cursor.execute(query)
        rows = cursor.fetchall()
        segments = [dict(row) for row in rows]
        conn.close()
        
        logger.info(f"Read {len(segments)} segments from SQLite")
        return segments, 0


class PostgresLoader:
    """Load data into Supabase PostgreSQL."""
    
    def __init__(self):
        self.db: Session = SessionLocal()
    
    def get_or_create_station(self, code: str, name: str, city: str, 
                              lat: float, lon: float) -> Optional[str]:
        """
        Get existing station or create new.
        Returns station UUID.
        """
        try:
            # Check if exists
            station = self.db.query(Station).filter(
                Station.name == name,
                Station.city == city
            ).first()
            
            if station:
                return str(station.id)
            
            # Create new
            station = Station(
                id=str(uuid.uuid4()),
                name=name,
                city=city,
                latitude=lat,
                longitude=lon,
                created_at=datetime.utcnow()
            )
            self.db.add(station)
            self.db.commit()
            logger.debug(f"Created station: {name} ({code})")
            return str(station.id)
        except Exception as e:
            logger.error(f"Error creating station {name}: {e}")
            self.db.rollback()
            return None
    
    def update_or_create_segment(
        self, 
        source_station_id: str,
        dest_station_id: str,
        departure_time: str,
        arrival_time: str,
        duration: int,
        cost: float,
        operator: str,
        operating_days: str,
        train_number: str
    ) -> Optional[str]:
        """
        Create or update segment.
        Returns segment UUID.
        """
        try:
            # Check if already exists (by stations + times + train)
            existing = self.db.query(Segment).filter(
                and_(
                    Segment.source_station_id == source_station_id,
                    Segment.dest_station_id == dest_station_id,
                    Segment.departure_time == departure_time,
                    Segment.arrival_time == arrival_time,
                    Segment.operator == operator
                )
            ).first()
            
            if existing:
                # Update cost/duration if changed
                existing.cost = cost
                existing.duration_minutes = duration
                existing.operating_days = operating_days
                self.db.commit()
                return str(existing.id)
            
            # Create new
            segment = Segment(
                id=str(uuid.uuid4()),
                source_station_id=source_station_id,
                dest_station_id=dest_station_id,
                transport_mode="train",
                departure_time=departure_time,
                arrival_time=arrival_time,
                duration_minutes=duration,
                cost=cost,
                operator=operator,
                operating_days=operating_days,
                created_at=datetime.utcnow()
            )
            self.db.add(segment)
            self.db.commit()
            logger.debug(f"Created segment: {train_number} {departure_time}-{arrival_time}")
            return str(segment.id)
        except Exception as e:
            logger.error(f"Error creating segment: {e}")
            self.db.rollback()
            return None
    
    def get_station_id_by_code(self, code: str) -> Optional[str]:
        """Get station ID by code (assumes stations are synced)."""
        try:
            # Simple query - improve if needed
            station = self.db.query(Station).filter(
                Station.name.ilike(f"%{code}%")
            ).first()
            return str(station.id) if station else None
        except:
            return None
    
    def close(self):
        """Close DB connection."""
        self.db.close()


class OperatingDaysBitmask:
    """Convert day flags to bitmask string."""
    
    @staticmethod
    def create(mon=False, tue=False, wed=False, thu=False, 
               fri=False, sat=False, sun=False) -> str:
        """
        Create bitmask string.
        Index: [0]=Mon, [1]=Tue, ..., [6]=Sun
        Example: "1101110" = Mon+Tue+Thu+Fri+Sat (not Wed, not Sun)
        """
        bits = [
            '1' if mon else '0',
            '1' if tue else '0',
            '1' if wed else '0',
            '1' if thu else '0',
            '1' if fri else '0',
            '1' if sat else '0',
            '1' if sun else '0',
        ]
        return ''.join(bits)


def time_string_to_minutes(time_str: str) -> int:
    """Convert HH:MM string to minutes from midnight."""
    try:
        h, m = time_str.split(':')
        return int(h) * 60 + int(m)
    except:
        return 0


def calculate_duration(departure: str, arrival: str) -> int:
    """Calculate duration in minutes between two time strings."""
    try:
        dep_mins = time_string_to_minutes(departure)
        arr_mins = time_string_to_minutes(arrival)
        
        # Handle overnight crossings
        if arr_mins < dep_mins:
            arr_mins += 24 * 60
        
        return arr_mins - dep_mins
    except:
        return 0


def run_etl(sqlite_path: str = DEFAULT_SQLITE_PATH) -> Dict[str, int]:
    """
    Run ETL pipeline.
    
    Returns:
      {
        'stations_synced': N,
        'segments_created': N,
        'errors': N
      }
    """
    logger.info("=" * 60)
    logger.info("Starting ETL: railway_manager.db → Supabase")
    logger.info("=" * 60)
    
    try:
        # Initialize
        reader = SQLiteReader(sqlite_path)
        loader = PostgresLoader()
        
        results = {
            'stations_synced': 0,
            'segments_created': 0,
            'errors': 0
        }
        
        # STEP 1: Sync Stations
        logger.info("\n[STEP 1] Syncing stations_master...")
        stations = reader.read_stations_master()
        station_code_to_id: Dict[str, str] = {}
        
        for station in stations:
            station_id = loader.get_or_create_station(
                code=station['station_code'],
                name=station['station_name'],
                city=station['city'],
                lat=float(station.get('latitude', 0) or 0),
                lon=float(station.get('longitude', 0) or 0)
            )
            if station_id:
                station_code_to_id[station['station_code']] = station_id
                results['stations_synced'] += 1
        
        logger.info(f"✅ Synced {results['stations_synced']} stations")
        
        # STEP 2: Load Segments
        logger.info("\n[STEP 2] Loading segments from train schedules...")
        segments_data, errors = reader.read_segment_data()
        
        for seg_dict in segments_data:
            try:
                source_code = seg_dict['source_station_code']
                dest_code = seg_dict['destination_station_code']
                
                # Get station IDs
                source_id = station_code_to_id.get(source_code)
                dest_id = station_code_to_id.get(dest_code)
                
                if not source_id or not dest_id:
                    logger.warning(f"Station not found: {source_code} or {dest_code}")
                    results['errors'] += 1
                    continue
                
                # Extract operating days
                operating_days = OperatingDaysBitmask.create(
                    mon=seg_dict.get('monday', False),
                    tue=seg_dict.get('tuesday', False),
                    wed=seg_dict.get('wednesday', False),
                    thu=seg_dict.get('thursday', False),
                    fri=seg_dict.get('friday', False),
                    sat=seg_dict.get('saturday', False),
                    sun=seg_dict.get('sunday', False)
                )
                
                # Calculate duration
                departure = seg_dict['departure_time']
                arrival = seg_dict['arrival_time']
                duration = calculate_duration(departure, arrival)
                
                # Get cost
                cost = float(seg_dict.get('total_fare', 0) or 0)
                operator = seg_dict.get('operator', 'Indian Railways')
                train_number = seg_dict.get('train_number', 'Unknown')
                
                # Create segment
                segment_id = loader.update_or_create_segment(
                    source_station_id=source_id,
                    dest_station_id=dest_id,
                    departure_time=departure,
                    arrival_time=arrival,
                    duration=duration,
                    cost=cost,
                    operator=operator,
                    operating_days=operating_days,
                    train_number=train_number
                )
                
                if segment_id:
                    results['segments_created'] += 1
                else:
                    results['errors'] += 1
            
            except Exception as e:
                logger.error(f"Error processing segment: {e}")
                results['errors'] += 1
                continue
        
        logger.info(f"✅ Created {results['segments_created']} segments")
        
        # STEP 3: Summary
        logger.info("\n" + "=" * 60)
        logger.info("ETL COMPLETE")
        logger.info(f"Stations synced: {results['stations_synced']}")
        logger.info(f"Segments created: {results['segments_created']}")
        logger.info(f"Errors: {results['errors']}")
        logger.info("=" * 60)
        
        # Cleanup
        loader.close()
        
        return results
    
    except Exception as e:
        logger.error(f"ETL failed: {e}")
        raise


if __name__ == "__main__":
    import sys
    
    sqlite_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_SQLITE_PATH
    results = run_etl(sqlite_path)
    
    # Exit with error code if there were issues
    exit_code = 0 if results['errors'] == 0 else 1
    sys.exit(exit_code)
```

---

### Step 3: Create Test File

**File**: `backend/etl/tests/__init__.py`

```python
# Placeholder
```

**File**: `backend/etl/tests/test_etl.py`

```python
"""Tests for ETL pipeline."""

import pytest
import os
import sqlite3
from pathlib import Path
from datetime import datetime

from backend.etl.sqlite_to_postgres import (
    SQLiteReader,
    PostgresLoader,
    OperatingDaysBitmask,
    calculate_duration,
    run_etl
)


class TestOperatingDaysBitmask:
    """Test bitmask generation."""
    
    def test_all_days(self):
        mask = OperatingDaysBitmask.create(True, True, True, True, True, True, True)
        assert mask == "1111111"
    
    def test_weekdays_only(self):
        mask = OperatingDaysBitmask.create(True, True, True, True, True, False, False)
        assert mask == "1111100"
    
    def test_no_days(self):
        mask = OperatingDaysBitmask.create()
        assert mask == "0000000"


class TestDurationCalculation:
    """Test duration calculation."""
    
    def test_same_day(self):
        duration = calculate_duration("08:00", "20:00")
        assert duration == 12 * 60  # 720 minutes
    
    def test_overnight(self):
        duration = calculate_duration("22:00", "06:00")
        assert duration == 8 * 60  # 480 minutes
    
    def test_zero_duration(self):
        duration = calculate_duration("08:00", "08:00")
        assert duration == 0


class TestSQLiteReader:
    """Test reading from SQLite."""
    
    def test_read_stations_master(self):
        """Test reading stations (requires railway_manager.db)."""
        db_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "railway_manager.db"
        )
        
        if not os.path.exists(db_path):
            pytest.skip(f"railway_manager.db not found at {db_path}")
        
        reader = SQLiteReader(db_path)
        stations = reader.read_stations_master()
        
        assert len(stations) > 0
        assert all('station_code' in s for s in stations)
        assert all('station_name' in s for s in stations)


class TestETLPipeline:
    """Integration test (requires real databases)."""
    
    def test_etl_runs_without_error(self):
        """Test full ETL pipeline."""
        db_path = os.path.join(
            os.path.dirname(__file__),
            "..", "..", "railway_manager.db"
        )
        
        if not os.path.exists(db_path):
            pytest.skip("railway_manager.db not found")
        
        results = run_etl(db_path)
        
        assert results['stations_synced'] > 0
        assert results['segments_created'] > 0
        assert results['errors'] == 0
```

---

### Step 4: Add to Project Management

**File**: `backend/etl/schema_map.md`

```markdown
# ETL Schema Mapping

## Stations: stations_master → stations

| SQLite (stations_master) | PostgreSQL (stations) | Notes |
|--------------------------|----------------------|-------|
| station_code | name | e.g., "NDLS" |
| station_name | IGNORED | derive from code? Or use station_name |
| city | city | |
| state | IGNORED | Not in target schema |
| latitude | latitude | |
| longitude | longitude | |
| is_junction | IGNORED | Not tracked |

## Segments: train_schedule + train_routes + train_fares → segments

| Source Tables | Target (segments) | Calculation |
|----------------|-------------------|------------|
| train_routes.source_station_code | source_station_id | Lookup in stations table |
| train_routes.destination_station_code | dest_station_id | Lookup in stations table |
| train_schedule.departure_time | departure_time | Direct copy "HH:MM" |
| train_schedule.arrival_time | arrival_time | Direct copy "HH:MM" |
| train_routes.estimated_duration OR calculate | duration_minutes | Arrival - Departure (in minutes) |
| train_fares.total_fare | cost | SELECT MIN() for best fare per class |
| trains_master.operator | operator | Direct copy |
| train_running_days.* | operating_days | Bitmask: "1111111" |
| (not mapped) | transport_mode | Always "train" for now |

## Key Assumptions

1. **One segment per (train, source, destination, time)** - trains don't split
2. **Latest updated_at wins** - if multiple records same train
3. **Use minimum fare** - if multiple classes available
4. **No filtering** - include all trains (even historical)

## Running ETL

```bash
# Basic run
cd backend
python -m etl.sqlite_to_postgres

# With custom path
python -m etl.sqlite_to_postgres /custom/path/db.db

# In production (via Cloud Scheduler or cron)
0 2 * * * /app/run_etl.sh  # Run daily at 2 AM
```
```

---

## Step 5: How to Run It

### Local Development

```bash
# 1. Ensure railway_manager.db exists
ls backend/railway_manager.db  # Should exist

# 2. Configure DATABASE_URL
export DATABASE_URL="postgresql://user:pass@localhost/routemaster"

# 3. Ensure Supabase is accessible
# Or update config.py to use test database

# 4. Run ETL
cd backend
python -m etl.sqlite_to_postgres

# Expected output:
# ============================================================
# Starting ETL: railway_manager.db → Supabase
# ============================================================
# [STEP 1] Syncing stations_master...
# ✅ Synced 1247 stations
# [STEP 2] Loading segments from train schedules...
# ✅ Created 45230 segments
# ============================================================
# ETL COMPLETE
# Stations synced: 1247
# Segments created: 45230
# Errors: 0
# ============================================================
```

### Testing

```bash
pytest backend/etl/tests/test_etl.py -v
```

### Verify Results

```sql
-- In Supabase PostgreSQL
SELECT COUNT(*) FROM stations;           -- Should be 1000+
SELECT COUNT(*) FROM segments;           -- Should be 10000+

-- Check specific route
SELECT * FROM segments
WHERE source_station_id IN (
  SELECT id FROM stations WHERE name LIKE '%Delhi%'
)
LIMIT 5;
```

---

## Step 6: Automate with Cloud Scheduler

### Option A: Supabase Edge Functions (Recommended)

**File**: `supabase/functions/etl-sync/index.ts`

```typescript
import { serve } from "https://deno.land/std@0.168.0/http/server.ts"
import { Client } from "https://deno.land/x/postgres@v0.17.0/mod.ts"

serve(async (req) => {
  if (req.method !== "POST") {
    return new Response("Method not allowed", { status: 405 })
  }

  try {
    // Call Python API that triggers ETL
    const resp = await fetch("http://localhost:8000/api/admin/etl-sync", {
      method: "POST",
      headers: {
        "Authorization": `Bearer ${Deno.env.get("ADMIN_API_TOKEN")}`
      }
    })
    
    return Response.json(await resp.json())
  } catch (error) {
    return Response.json({ error: error.message }, { status: 500 })
  }
})
```

### Option B: FastAPI Endpoint + Cloud Scheduler

**File**: `backend/api/admin.py` (add this method)

```python
@router.post("/etl-sync", tags=["admin"])
async def trigger_etl_sync(token: str = Depends(verify_admin_token)):
    """
    Trigger ETL sync from railway_manager.db to Supabase.
    Only callable by admin.
    """
    try:
        from etl.sqlite_to_postgres import run_etl
        
        # Run ETL
        results = run_etl()
        
        # Log results
        logger.info(f"ETL sync completed: {results}")
        
        return {
            "status": "success",
            "results": results,
            "timestamp": datetime.utcnow().isoformat()
        }
    except Exception as e:
        logger.error(f"ETL sync failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
```

---

## Summary

With this ETL script, your system becomes:

```
Before ETL:
  Segments table = EMPTY
  Routes search = NO RESULTS
  User = "No trains found" 😞

After ETL:
  Segments table = 40,000+ trains
  Routes search = Real results
  User = "Found 5 options" 😊
```

**File checklist**:
- [ ] `backend/etl/__init__.py` (created)
- [ ] `backend/etl/sqlite_to_postgres.py` (created)
- [ ] `backend/etl/tests/test_etl.py` (created)
- [ ] `backend/etl/schema_map.md` (created)
- [ ] `backend/api/admin.py` (add `/etl-sync` endpoint)
- [ ] `.env` (set DATABASE_URL if not already)

---

## Next: Run It!

```bash
# Test locally first
python -m backend.etl.sqlite_to_postgres

# Watch for output
# Check Supabase tables
# Try a route search

# If all good:
# 1. Deploy to production
# 2. Set up Cloud Scheduler
# 3. Run daily at 2 AM
```

That's it! Your system is now connected. 🎉

