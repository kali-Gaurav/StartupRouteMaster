"""Add booking_fraud_checks table for fraud detection integration

Revision ID: abc123def456
Revises: ff2a3b4c5d6
Create Date: 2026-02-20 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision = 'abc123def456'
down_revision = 'ff2a3b4c5d6'
branch_labels = None
depends_on = None


def upgrade() -> None:
    """Upgrade schema - create booking_fraud_checks table."""
    from sqlalchemy.exc import ProgrammingError
    try:
        op.create_table(
            'booking_fraud_checks',
            sa.Column('id', sa.String(36), primary_key=True, default=lambda: str(uuid.uuid4())),
            sa.Column('booking_id', sa.String(36), sa.ForeignKey('bookings.id'), nullable=False, index=True),
            sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=False, index=True),
            sa.Column('check_type', sa.String(50), nullable=False),
            sa.Column('risk_score', sa.Float, nullable=False),
            sa.Column('flags', sa.JSON, nullable=True),
            sa.Column('decision', sa.String(20), nullable=False),
            sa.Column('created_at', sa.DateTime(), nullable=False, server_default=sa.func.now()),
        )
        # Create indexes for efficient querying
        op.create_index('ix_booking_fraud_checks_booking_id', 'booking_fraud_checks', ['booking_id'])
        op.create_index('ix_booking_fraud_checks_user_id', 'booking_fraud_checks', ['user_id'])
        op.create_index('ix_booking_fraud_checks_check_type', 'booking_fraud_checks', ['check_type'])
    except ProgrammingError:
        pass


def downgrade() -> None:
    """Downgrade schema - drop booking_fraud_checks table."""
    op.drop_index('ix_booking_fraud_checks_check_type', table_name='booking_fraud_checks')
    op.drop_index('ix_booking_fraud_checks_user_id', table_name='booking_fraud_checks')
    op.drop_index('ix_booking_fraud_checks_booking_id', table_name='booking_fraud_checks')
    op.drop_table('booking_fraud_checks')
