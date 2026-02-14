"""initial schema

Revision ID: 0001_initial
Revises: 
Create Date: 2026-02-14 00:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '0001_initial'
down_revision = None
branch_labels = None
depends_on = None


def upgrade() -> None:
    # autogenerate produced no operations or migrations are managed elsewhere
    pass


def downgrade() -> None:
    pass
