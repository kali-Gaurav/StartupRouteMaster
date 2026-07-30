"""manual_intelligence_hardening

Revision ID: 36c391b0bb6f
Revises: 666666666666
Create Date: 2026-04-14 22:22:17.110700

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '36c391b0bb6f'
down_revision: Union[str, Sequence[str], None] = '666666666666'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. New Tables for P18 Settlement & P5 Karma
    # op.create_table IF NOT EXISTS equivalent for Alembic/Postgres
    op.execute("CREATE TABLE IF NOT EXISTS wallets (id VARCHAR(36) NOT NULL, user_id VARCHAR(36), balance FLOAT, total_earned FLOAT, updated_at TIMESTAMP WITHOUT TIME ZONE, PRIMARY KEY (id), UNIQUE (user_id), FOREIGN KEY(user_id) REFERENCES users (id))")
    op.execute("CREATE TABLE IF NOT EXISTS credit_transactions (id VARCHAR(36) NOT NULL, wallet_id VARCHAR(36), amount FLOAT NOT NULL, type VARCHAR(20), reason VARCHAR(255), reference_id VARCHAR(100), timestamp TIMESTAMP WITHOUT TIME ZONE, PRIMARY KEY (id), FOREIGN KEY(wallet_id) REFERENCES wallets (id))")

    # 2. Column Updates for P11 Multi-Modal Intelligence
    # We use a try-except block in raw SQL or similar for columns
    op.execute("ALTER TABLE station_realtime_heartbeats ADD COLUMN IF NOT EXISTS station_mode VARCHAR(20) DEFAULT 'RAIL'")
    op.execute("ALTER TABLE station_realtime_heartbeats ADD COLUMN IF NOT EXISTS connectivity_score FLOAT DEFAULT 1.0")
    op.execute("ALTER TABLE station_realtime_heartbeats ADD COLUMN IF NOT EXISTS sync_hash VARCHAR(64)")


def downgrade() -> None:
    # Downgrade is optional in hardening scripts but kept for symmetry
    try:
        op.drop_column('station_realtime_heartbeats', 'sync_hash')
        op.drop_column('station_realtime_heartbeats', 'connectivity_score')
        op.drop_column('station_realtime_heartbeats', 'station_mode')
        op.drop_table('credit_transactions')
        op.drop_table('wallets')
    except: pass
