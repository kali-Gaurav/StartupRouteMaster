"""Add only realtime_data and rl_feedback_logs tables

Revision ID: 71c935cd207c
Revises: 707650e38917
Create Date: 2026-02-15 00:20:36.345802

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '71c935cd207c'
down_revision: Union[str, Sequence[str], None] = '162f7ad310af'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('realtime_data',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('event_type', sa.String(length=50), nullable=False),
    sa.Column('entity_type', sa.String(length=50), nullable=False),
    sa.Column('entity_id', sa.String(length=100), nullable=False),
    sa.Column('data', sa.JSON(), nullable=False),
    sa.Column('timestamp', sa.DateTime(), nullable=False),
    sa.Column('source', sa.String(length=100), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_realtime_data_entity_id'), 'realtime_data', ['entity_id'], unique=False)
    op.create_index(op.f('ix_realtime_data_event_type'), 'realtime_data', ['event_type'], unique=False)
    op.create_index(op.f('ix_realtime_data_timestamp'), 'realtime_data', ['timestamp'], unique=False)
    op.create_table('rl_feedback_logs',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=True),
    sa.Column('session_id', sa.String(length=36), nullable=False),
    sa.Column('action', sa.String(length=100), nullable=False),
    sa.Column('context', sa.JSON(), nullable=False),
    sa.Column('reward', sa.Float(), nullable=False),
    sa.Column('timestamp', sa.DateTime(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_rl_feedback_logs_session_id'), 'rl_feedback_logs', ['session_id'], unique=False)
    op.create_index(op.f('ix_rl_feedback_logs_timestamp'), 'rl_feedback_logs', ['timestamp'], unique=False)
    op.create_index(op.f('ix_rl_feedback_logs_user_id'), 'rl_feedback_logs', ['user_id'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    pass
