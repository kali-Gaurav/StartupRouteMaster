"""Add trip_id, distance_km and convert times to TIME on segments

Revision ID: a9b8c7d6e5f4
Revises: f1234567890a
Create Date: 2026-02-19 00:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'a9b8c7d6e5f4'
down_revision: Union[str, Sequence[str], None] = 'f1234567890a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema: add trip_id, distance_km, arrival_day_offset; convert time columns; add index."""
    # Add nullable columns first
    op.add_column('segments', sa.Column('trip_id', sa.Integer(), nullable=True))
    op.add_column('segments', sa.Column('distance_km', sa.Float(), nullable=True))
    op.add_column('segments', sa.Column('arrival_day_offset', sa.Integer(), nullable=True))

    # Create FK to trips (Postgres only - will be ignored by SQLite offline runs)
    op.create_foreign_key('fk_segments_trip_id_trips', 'segments', 'trips', ['trip_id'], ['id'])

    # Convert departure_time/arrival_time from varchar to time where supported
    # The USING expression tolerates existing 'HH:MM' strings.
    try:
        op.execute("ALTER TABLE segments ALTER COLUMN departure_time TYPE time USING (substring(departure_time from 1 for 5))::time;")
        op.execute("ALTER TABLE segments ALTER COLUMN arrival_time TYPE time USING (substring(arrival_time from 1 for 5))::time;")
    except Exception:
        # Some DBs (SQLite) won't support ALTER TYPE; skip at runtime.
        pass

    # Add composite index for fast lookups
    op.create_index('idx_segments_src_dest_dep', 'segments', ['source_station_id', 'dest_station_id', 'departure_time'])


def downgrade() -> None:
    """Downgrade: revert schema changes."""
    # Drop composite index
    op.drop_index('idx_segments_src_dest_dep', table_name='segments')

    # Revert time columns back to VARCHAR(8) where possible
    try:
        op.execute("ALTER TABLE segments ALTER COLUMN departure_time TYPE VARCHAR(8) USING to_char(departure_time, 'HH24:MI');")
        op.execute("ALTER TABLE segments ALTER COLUMN arrival_time TYPE VARCHAR(8) USING to_char(arrival_time, 'HH24:MI');")
    except Exception:
        pass

    # Drop FK and added columns
    try:
        op.drop_constraint('fk_segments_trip_id_trips', 'segments', type_='foreignkey')
    except Exception:
        pass
    op.drop_column('segments', 'trip_id')
    op.drop_column('segments', 'distance_km')
    op.drop_column('segments', 'arrival_day_offset')
