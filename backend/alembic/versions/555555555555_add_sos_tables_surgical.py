"""Add SOS tables surgically

Revision ID: 555555555555
Revises: add_user_verification_v1
Create Date: 2026-04-12 21:55:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision = '555555555555'
down_revision = 'add_user_verification_v1'
branch_labels = None
depends_on = None

def upgrade() -> None:
    # 1. Create sos_events table
    op.create_table('sos_events',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=True),
        sa.Column('status', sa.String(length=20), nullable=True),
        sa.Column('priority', sa.String(length=20), nullable=True),
        sa.Column('category', sa.String(length=50), nullable=True),
        sa.Column('extra', sa.Text(), nullable=True),
        sa.Column('triggered_at', sa.DateTime(), nullable=True),
        sa.Column('resolved_at', sa.DateTime(), nullable=True),
        sa.Column('acknowledged_at', sa.DateTime(), nullable=True),
        sa.Column('escalation_level', sa.Integer(), nullable=True),
        sa.Column('call_logs', sa.JSON(), nullable=True),
        sa.Column('chat_history', sa.JSON(), nullable=True),
        sa.Column('structured_info', sa.JSON(), nullable=True),
        sa.Column('active_participants', sa.JSON(), nullable=True),
        sa.Column('trip_data', sa.JSON(), nullable=True),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sos_events_user_id'), 'sos_events', ['user_id'], unique=False)

    # 2. Create sos_telemetry table
    op.create_table('sos_telemetry',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('event_id', sa.String(length=36), nullable=True),
        sa.Column('lat', sa.Float(), nullable=False),
        sa.Column('lng', sa.Float(), nullable=False),
        sa.Column('battery_level', sa.Float(), nullable=True),
        sa.Column('timestamp', sa.DateTime(), nullable=True),
        sa.ForeignKeyConstraint(['event_id'], ['sos_events.id'], ),
        sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_sos_telemetry_event_id'), 'sos_telemetry', ['event_id'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_sos_telemetry_event_id'), table_name='sos_telemetry')
    op.drop_table('sos_telemetry')
    op.drop_index(op.f('ix_sos_events_user_id'), table_name='sos_events')
    op.drop_table('sos_events')
