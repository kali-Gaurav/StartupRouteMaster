# Database Structure and Organization

This directory contains all database files for the RouteMaster backend system.

## Database Files

### 1. **railway_data.db** (~123 MB)
- **Type**: SQLite database
- **Purpose**: Source database containing human-readable railway scheduling data
- **Usage**: 
  - Primary data source for ETL (Extract, Transform, Load) operations
  - Synced to PostgreSQL via `backend/etl/sqlite_to_postgres.py`
  - Scheduled monthly ETL sync at 2 AM on the 1st of each month
- **Tables**: Stations, train routes, schedules, segments, time indices, etc.
- **Access**: Read-only via ETL processes; manually updated with latest railway data

### 2. **transit_graph.db** (~88 MB)
- **Type**: SQLite database  
- **Purpose**: Algorithm-optimized database for route engine calculations
- **Usage**: 
  - Used by route optimization engine (`backend/core/route_engine.py`)
  - Stores pre-computed routing graphs and segments
  - Improves performance of real-time search operations
- **Tables**: Optimized transit graph structures
- **Access**: Read-based queries during route searches

## Architecture Overview

```
backend/database/
├── __init__.py
├── config.py           # Database configuration
├── models.py           # SQLAlchemy ORM models
├── session.py          # Database session management
├── railway_data.db     # SQLite: Source data (ETL input)
├── transit_graph.db    # SQLite: Routing optimizations
└── README.md           # This file
```

## Data Flow

```
railway_data.db (SQLite Source)
        ↓
backend/etl/sqlite_to_postgres.py
        ↓
PostgreSQL (Production Database)
        ↓
backend/core/route_engine.py (uses transit_graph.db for optimization)
        ↓
Real-time API Responses
```

## Important Notes

1. **All .db files must be placed in `backend/database/`** - This ensures:
   - Centralized database management
   - Consistent file organization
   - Proper .gitignore handling
   - Easy backup and migration

2. **PostgreSQL is the primary database** - SQLite databases are:
   - Offline/backup sources
   - Performance optimization stores
   - Never used as primary transactional database

3. **ETL Sync Schedule**:
   - Monthly: Every 1st of month at 2:00 AM UTC
   - Triggered via: `POST /api/admin/etl-sync?token=<ADMIN_TOKEN>`
   - Manually: Call `backend/etl/sqlite_to_postgres.py`

4. **File Size References**:
   - `railway_data.db`: ~123 MB (expected to grow as routes/schedules added)
   - `transit_graph.db`: ~88 MB (used for routing optimization)

## Accessing Databases

### Direct SQLite Access (Development Only)
```python
import sqlite3
conn = sqlite3.connect('backend/database/railway_data.db')
cursor = conn.cursor()
cursor.execute("SELECT * FROM stations LIMIT 5")
```

### Via Python Script
```bash
# Inspect database schema
python backend/inspect_railway_db.py

# Check database connectivity
python check_db.py
```

### Production Access
- Use PostgreSQL connection (primary database)
- SQLite databases are read-only/reference only
- ETL keeps PostgreSQL synchronized

## Backup and Restore

### Backup
```bash
# Backup all SQLite databases
cp backend/database/*.db backups/
```

### Restore
```bash
# Restore from backup
cp backups/*.db backend/database/
```

## Configuration

Database paths are centralized in code:
- **ETL**: `backend/etl/sqlite_to_postgres.py` → `backend/database/railway_data.db`  
- **Route Engine**: `backend/core/route_engine.py` → `backend/database/transit_graph.db`
- **PostgreSQL**: `backend/database/config.py` → `Config.DATABASE_URL`

## Troubleshooting

### Database Not Found Errors
- Check that files exist in `backend/database/`
- Verify paths in code reference `backend/database/` (not `backend/business/`)
- Confirm `.db` files have proper permissions (readable)

### ETL Failures
- Verify `railway_data.db` exists and is readable
- Check PostgreSQL connection in `Config.DATABASE_URL`
- Review logs: `backend/etl/sqlite_to_postgres.py`

### Route Engine Errors
- Ensure `transit_graph.db` exists and has expected tables
- Check route engine initialization logs
- Verify PostgreSQL synchronization is complete

## Related Files

- **ETL Module**: `backend/etl/sqlite_to_postgres.py`
- **Route Engine**: `backend/core/route_engine.py`
- **Configuration**: `backend/database/config.py`
- **Session Management**: `backend/database/session.py`
- **ORM Models**: `backend/database/models.py`
