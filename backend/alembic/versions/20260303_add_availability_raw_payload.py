"""add raw_payload and extra fields to train_availability_cache

Revision ID: 20260303_add_availability_raw_payload
Revises: 41af9fd39336
Create Date: 2026-03-03 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260303_add_availability_raw_payload'
down_revision = '41af9fd39336'
branch_labels = None
depends_on = None


def upgrade():
    op.add_column('train_availability_cache', sa.Column('raw_payload', sa.Text(), nullable=True))
    op.add_column('train_availability_cache', sa.Column('ticket_fare', sa.Integer(), nullable=True))
    op.add_column('train_availability_cache', sa.Column('catering_charge', sa.Integer(), nullable=True))
    op.add_column('train_availability_cache', sa.Column('alt_cnf_seat', sa.Boolean(), nullable=True))
    op.add_column('train_availability_cache', sa.Column('alt_seat_status', sa.String(length=100), nullable=True))
    op.add_column('train_availability_cache', sa.Column('alt_seat_fare', sa.Integer(), nullable=True))


def downgrade():
    op.drop_column('train_availability_cache', 'alt_seat_fare')
    op.drop_column('train_availability_cache', 'alt_seat_status')
    op.drop_column('train_availability_cache', 'alt_cnf_seat')
    op.drop_column('train_availability_cache', 'catering_charge')
    op.drop_column('train_availability_cache', 'ticket_fare')
    op.drop_column('train_availability_cache', 'raw_payload')
