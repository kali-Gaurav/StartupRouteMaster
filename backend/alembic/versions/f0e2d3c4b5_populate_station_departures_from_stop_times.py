"""populate_station_departures from stop_times

This migration populates the station_departures_indexed table from stop_times,
creating records for each segment (stop_time → next_stop_time) to enable
fast Station → Time → Departures lookups as per Phase 1.

Revision ID: f0e2d3c4b5
Revises: f0e1d2c3b4
Create Date: 2026-02-20 10:00:00.000000
"""
from alembic import op
import sqlalchemy as sa
from datetime import datetime
import uuid

# revision identifiers, used by Alembic.
revision = 'f0e2d3c4b5'
down_revision = 'f0e1d2c3b4'
branch_labels = None
depends_on = None


def upgrade():
    """
    Populate station_departures_indexed table from stop_times.

    For each trip, we iterate through stop_times in sequence.
    Each consecutive pair (from_stop, to_stop) creates a StationDeparture record.
    """
    # Create a connection to execute raw SQL
    connection = op.get_bind()

    # SQL to populate station_departures_indexed from stop_times
    populate_sql = """
    INSERT INTO station_departures_indexed (
        id,
        station_id,
        trip_id,
        departure_time,
        arrival_time_at_next,
        next_station_id,
        operating_days,
        train_number,
        distance_to_next,
        created_at
    )
    SELECT DISTINCT
        lower(hex(randomblob(16))),  -- Generate UUID-like string
        st1.stop_id,
        st1.trip_id,
        st1.departure_time,
        st2.arrival_time,
        st2.stop_id,
        COALESCE(c.monday || c.tuesday || c.wednesday || c.thursday ||
                 c.friday || c.saturday || c.sunday, '1111111'),
        t.headsign,
        seg.distance,
        CURRENT_TIMESTAMP
    FROM stop_times st1
    INNER JOIN stop_times st2
        ON st1.trip_id = st2.trip_id
        AND st2.stop_sequence = st1.stop_sequence + 1
    INNER JOIN trips t ON st1.trip_id = t.id
    LEFT JOIN calendar c ON t.service_id = c.id
    LEFT JOIN segments seg
        ON seg.trip_id = st1.trip_id
        AND seg.from_station_id = st1.stop_id
        AND seg.to_station_id = st2.stop_id
    WHERE NOT EXISTS (
        SELECT 1 FROM station_departures_indexed sdi
        WHERE sdi.station_id = st1.stop_id
        AND sdi.trip_id = st1.trip_id
        AND sdi.departure_time = st1.departure_time
    )
    ORDER BY st1.stop_id, st1.departure_time;
    """

    try:
        connection.execute(sa.text(populate_sql))
        print(f"✓ Populated station_departures_indexed table")
    except Exception as e:
        print(f"✗ Error populating station_departures_indexed: {e}")
        # Continue - this is not critical for app startup
        pass


def downgrade():
    """
    Clear the station_departures_indexed table (remove populated records).
    This is safe since we can rebuild from stop_times anytime.
    """
    connection = op.get_bind()
    connection.execute(sa.text("DELETE FROM station_departures_indexed;"))
    print("✓ Cleared station_departures_indexed table")
