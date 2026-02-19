"""add station_departures and time_index_keys tables

Revision ID: ff2a3b4c5d6
Revises: a9b8c7d6e5f4
Create Date: 2026-02-19 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'ff2a3b4c5d6'
down_revision = 'a9b8c7d6e5f4'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'time_index_keys',
        sa.Column('id', sa.Integer(), primary_key=True),
        sa.Column('entity_type', sa.String(length=50), nullable=False),
        sa.Column('entity_id', sa.String(length=255), nullable=False),
        sa.UniqueConstraint('entity_type', 'entity_id', name='uq_time_index_key')
    )
    op.create_index('idx_time_index_entity', 'time_index_keys', ['entity_type', 'entity_id'])

    op.create_table(
        'station_departures',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('station_id', sa.String(length=36), nullable=False),
        sa.Column('bucket_start_minute', sa.Integer(), nullable=False),
        sa.Column('bitmap', sa.LargeBinary(), nullable=False),
        sa.Column('trips_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('station_id', 'bucket_start_minute', name='uq_station_bucket')
    )
    op.create_index('idx_station_departures_station_bucket', 'station_departures', ['station_id', 'bucket_start_minute'])


def downgrade():
    op.drop_index('idx_station_departures_station_bucket', table_name='station_departures')
    op.drop_table('station_departures')
    op.drop_index('idx_time_index_entity', table_name='time_index_keys')
    op.drop_table('time_index_keys')
