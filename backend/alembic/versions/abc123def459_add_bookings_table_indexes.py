"""Add indexes to bookings table for query optimization

Revision ID: abc123def459
Revises: ff2a3b4c5d6
Create Date: 2025-01-01 12:00:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = 'abc123def459'
down_revision: Union[str, Sequence[str], None] = 'ff2a3b4c5d6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema by adding indexes to bookings table."""
    # Composite index for user booking history queries (user_id + travel_date)
    op.execute(
        'CREATE INDEX IF NOT EXISTS idx_bookings_user_travel_date ON bookings (user_id, travel_date);'
    )
    
    # Index on booking_status for filtering by status
    op.execute(
        'CREATE INDEX IF NOT EXISTS idx_bookings_status ON bookings (booking_status);'
    )


def downgrade() -> None:
    """Downgrade schema by removing indexes from bookings table."""
    op.execute('DROP INDEX IF EXISTS idx_bookings_status;')
    op.execute('DROP INDEX IF EXISTS idx_bookings_user_travel_date;')
