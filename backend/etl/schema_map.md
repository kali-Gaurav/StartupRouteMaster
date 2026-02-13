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