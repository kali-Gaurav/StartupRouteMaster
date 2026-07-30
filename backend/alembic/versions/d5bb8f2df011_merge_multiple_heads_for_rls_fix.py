"""Merge multiple heads for RLS fix

Revision ID: d5bb8f2df011
Revises: 20260226_supabase, 20260303_add_availability_raw_payload, c3d4e5f6a7b8, b2c3d4e5f6a7
Create Date: 2026-03-11 18:30:27.947322

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'd5bb8f2df011'
down_revision: Union[str, Sequence[str], None] = ('20260226_supabase', '20260303_add_availability_raw_payload', 'c3d4e5f6a7b8', 'b2c3d4e5f6a7')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
