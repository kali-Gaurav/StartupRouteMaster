"""Add route_search_logs table for ML training

Revision ID: f1234567890a
Revises: e5887621aa5b
Create Date: 2026-02-15 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'f1234567890a'
down_revision: Union[str, Sequence[str], None] = 'e5887621aa5b'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table('route_search_logs',
        sa.Column('id', sa.String(36), primary_key=True, default=sa.text("gen_random_uuid()")),
        sa.Column('user_id', sa.String(36), sa.ForeignKey('users.id'), nullable=True, index=True),
        sa.Column('src', sa.String(255), nullable=False),
        sa.Column('dst', sa.String(255), nullable=False),
        sa.Column('date', sa.Date(), nullable=False),
        sa.Column('routes_shown', sa.JSON(), nullable=False),
        sa.Column('route_clicked', sa.String(36), nullable=True),
        sa.Column('booking_success', sa.Boolean(), nullable=True),
        sa.Column('latency_ms', sa.Float(), nullable=False),
        sa.Column('created_at', sa.DateTime(), default=sa.func.now()),
    )
    op.create_index('idx_route_search_logs_user_id', 'route_search_logs', ['user_id'])
    op.create_index('idx_route_search_logs_src_dst', 'route_search_logs', ['src', 'dst'])
    op.create_index('idx_route_search_logs_date', 'route_search_logs', ['date'])


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index('idx_route_search_logs_date', 'route_search_logs')
    op.drop_index('idx_route_search_logs_src_dst', 'route_search_logs')
    op.drop_index('idx_route_search_logs_user_id', 'route_search_logs')
    op.drop_table('route_search_logs')