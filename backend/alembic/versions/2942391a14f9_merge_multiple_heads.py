"""Merge multiple heads

Revision ID: 2942391a14f9
Revises: 3207f768fa56, a1b2c3d4e5f7, abc123def456, abc123def459
Create Date: 2026-05-04 23:21:56.047736

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2942391a14f9'
down_revision: Union[str, Sequence[str], None] = ('3207f768fa56', 'a1b2c3d4e5f7', 'abc123def456', 'abc123def459')
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    pass


def downgrade() -> None:
    """Downgrade schema."""
    pass
