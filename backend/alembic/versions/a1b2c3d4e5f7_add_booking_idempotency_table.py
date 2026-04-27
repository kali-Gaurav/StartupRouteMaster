"""Add booking_idempotency table for duplicate booking prevention

Revision ID: a1b2c3d4e5f7
Revises: ff2a3b4c5d6
Create Date: 2026-02-20 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision = 'a1b2c3d4e5f7'
down_revision = 'ff2a3b4c5d6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        'booking_idempotency',
        sa.Column('idempotency_key', sa.String(length=255), primary_key=True),
        sa.Column('booking_id', sa.String(36), sa.ForeignKey('bookings.id'), nullable=False),
        sa.Column('request_hash', sa.String(64), nullable=False),
        sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column('expires_at', sa.DateTime(), nullable=False),
    )
    op.create_index('ix_booking_idempotency_idempotency_key', 'booking_idempotency', ['idempotency_key'], unique=True)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('ix_booking_idempotency_idempotency_key', table_name='booking_idempotency')
    op.drop_table('booking_idempotency')