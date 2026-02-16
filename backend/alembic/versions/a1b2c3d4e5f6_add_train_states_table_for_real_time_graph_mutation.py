"""Add train_states table for real-time graph mutation

Revision ID: a1b2c3d4e5f6
Revises: 71c935cd207c
Create Date: 2026-02-16 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, Sequence[str], None] = '71c935cd207c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('train_states',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('trip_id', sa.Integer(), nullable=False),
    sa.Column('train_number', sa.String(length=50), nullable=False),
    sa.Column('current_station_id', sa.Integer(), nullable=True),
    sa.Column('next_station_id', sa.Integer(), nullable=True),
    sa.Column('delay_minutes', sa.Integer(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('platform_number', sa.String(length=10), nullable=True),
    sa.Column('last_updated', sa.DateTime(), nullable=False),
    sa.Column('estimated_arrival', sa.DateTime(), nullable=True),
    sa.Column('estimated_departure', sa.DateTime(), nullable=True),
    sa.Column('occupancy_rate', sa.Float(), nullable=False),
    sa.Column('cancelled_stations', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['current_station_id'], ['stops.id'], ),
    sa.ForeignKeyConstraint(['next_station_id'], ['stops.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('trip_id')
    )
    op.create_index(op.f('ix_train_states_trip_id'), 'train_states', ['trip_id'], unique=True)
    op.create_index(op.f('ix_train_states_status'), 'train_states', ['status'], unique=False)
    op.create_index(op.f('ix_train_states_last_updated'), 'train_states', ['last_updated'], unique=False)
    op.create_index(op.f('ix_train_states_train_number'), 'train_states', ['train_number'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_train_states_train_number'), table_name='train_states')
    op.drop_index(op.f('ix_train_states_last_updated'), table_name='train_states')
    op.drop_index(op.f('ix_train_states_status'), table_name='train_states')
    op.drop_index(op.f('ix_train_states_trip_id'), table_name='train_states')
    op.drop_table('train_states')