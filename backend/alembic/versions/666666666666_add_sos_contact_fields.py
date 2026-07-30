"""Add SOS contact fields

Revision ID: 666666666666
Revises: 555555555555
Create Date: 2026-04-12 21:58:00.000000

"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision = '666666666666'
down_revision = '555555555555'
branch_labels = None
depends_on = None

def upgrade() -> None:
    op.add_column('sos_events', sa.Column('name', sa.String(length=255), nullable=True))
    op.add_column('sos_events', sa.Column('phone', sa.String(length=20), nullable=True))
    op.add_column('sos_events', sa.Column('email', sa.String(length=255), nullable=True))
    op.add_column('sos_events', sa.Column('lat', sa.Float(), nullable=True))
    op.add_column('sos_events', sa.Column('lng', sa.Float(), nullable=True))
    op.create_index(op.f('ix_sos_events_phone'), 'sos_events', ['phone'], unique=False)

def downgrade() -> None:
    op.drop_index(op.f('ix_sos_events_phone'), table_name='sos_events')
    op.drop_column('sos_events', 'lng')
    op.drop_column('sos_events', 'lat')
    op.drop_column('sos_events', 'email')
    op.drop_column('sos_events', 'phone')
    op.drop_column('sos_events', 'name')
