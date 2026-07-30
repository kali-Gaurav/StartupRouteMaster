"""add stop_departures table for GTFS stop-centric time buckets

Revision ID: f0e1d2c3b4
Revises: ff2a3b4c5d6
Create Date: 2026-02-19 00:00:00.000001
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'f0e1d2c3b4'
down_revision = 'ff2a3b4c5d6'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'stop_departures',
        sa.Column('id', sa.String(length=36), primary_key=True),
        sa.Column('stop_id', sa.Integer(), nullable=False),
        sa.Column('bucket_start_minute', sa.Integer(), nullable=False),
        sa.Column('bitmap', sa.LargeBinary(), nullable=False),
        sa.Column('trips_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.DateTime(), nullable=False),
        sa.UniqueConstraint('stop_id', 'bucket_start_minute', name='uq_stop_bucket')
    )
    op.create_index('idx_stop_departures_stop_bucket', 'stop_departures', ['stop_id', 'bucket_start_minute'])


def downgrade():
    op.drop_index('idx_stop_departures_stop_bucket', table_name='stop_departures')
    op.drop_table('stop_departures')
