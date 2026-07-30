"""Add verification columns to users

Revision ID: add_user_verification_v1
Revises: enable_rls_v1
Create Date: 2026-03-11 19:15:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_user_verification_v1'
down_revision: Union[str, Sequence[str], None] = 'enable_rls_v1'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add columns to users table
    op.add_column('users', sa.Column('is_verified', sa.Boolean(), server_default='false', nullable=False))
    op.add_column('users', sa.Column('verified_at', sa.DateTime(), nullable=True))


def downgrade() -> None:
    # Remove columns from users table
    op.drop_column('users', 'verified_at')
    op.drop_column('users', 'is_verified')
