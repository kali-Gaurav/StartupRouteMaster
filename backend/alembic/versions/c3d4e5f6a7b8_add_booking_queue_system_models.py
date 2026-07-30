"""Add booking queue system models

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-02-23 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql

# revision identifiers, used by Alembic.
revision: str = 'c3d4e5f6a7b8'
down_revision: Union[str, Sequence[str], None] = 'f0e2d3c4b5'  # Latest migration
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Add booking queue system tables."""
    
    # Create booking_requests table
    op.create_table('booking_requests',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('source_station', sa.String(length=20), nullable=False),
    sa.Column('destination_station', sa.String(length=20), nullable=False),
    sa.Column('journey_date', sa.Date(), nullable=False),
    sa.Column('train_number', sa.String(length=20), nullable=False),
    sa.Column('train_name', sa.String(length=100), nullable=True),
    sa.Column('class_type', sa.String(length=10), nullable=False, server_default='AC_THREE_TIER'),
    sa.Column('quota', sa.String(length=10), nullable=False, server_default='GENERAL'),
    sa.Column('status', sa.String(length=20), nullable=False, server_default='PENDING'),
    sa.Column('verification_status', sa.String(length=20), nullable=False, server_default='NOT_VERIFIED'),
    sa.Column('payment_id', sa.String(length=36), nullable=True),
    sa.Column('route_details', postgresql.JSON(astext_type=sa.Text()), nullable=True),
    sa.Column('verification_data', postgresql.JSON(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.Column('verified_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.ForeignKeyConstraint(['payment_id'], ['payments.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_booking_requests_user', 'booking_requests', ['user_id'], unique=False)
    op.create_index('idx_booking_requests_status', 'booking_requests', ['status'], unique=False)
    op.create_index('idx_booking_requests_verification', 'booking_requests', ['verification_status'], unique=False)
    op.create_index('idx_booking_requests_created', 'booking_requests', ['created_at'], unique=False)
    op.create_index('idx_booking_requests_journey_date', 'booking_requests', ['journey_date'], unique=False)

    # Create booking_request_passengers table
    op.create_table('booking_request_passengers',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('booking_request_id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('age', sa.Integer(), nullable=False),
    sa.Column('gender', sa.String(length=10), nullable=False),
    sa.Column('berth_preference', sa.String(length=20), nullable=True),
    sa.Column('id_proof_type', sa.String(length=20), nullable=True),
    sa.Column('id_proof_number', sa.String(length=50), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['booking_request_id'], ['booking_requests.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_request_passengers_request', 'booking_request_passengers', ['booking_request_id'], unique=False)

    # Create booking_queue table
    op.create_table('booking_queue',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('booking_request_id', sa.String(length=36), nullable=False),
    sa.Column('priority', sa.Integer(), nullable=False, server_default='5'),
    sa.Column('execution_mode', sa.String(length=20), nullable=False, server_default='MANUAL'),
    sa.Column('status', sa.String(length=20), nullable=False, server_default='WAITING'),
    sa.Column('scheduled_time', sa.DateTime(), nullable=True),
    sa.Column('started_at', sa.DateTime(), nullable=True),
    sa.Column('completed_at', sa.DateTime(), nullable=True),
    sa.Column('executed_by', sa.String(length=36), nullable=True),
    sa.Column('execution_notes', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['booking_request_id'], ['booking_requests.id'], ),
    sa.ForeignKeyConstraint(['executed_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('booking_request_id')
    )
    op.create_index('idx_booking_queue_status', 'booking_queue', ['status'], unique=False)
    op.create_index('idx_booking_queue_priority', 'booking_queue', ['priority'], unique=False)
    op.create_index('idx_booking_queue_scheduled', 'booking_queue', ['scheduled_time'], unique=False)

    # Create booking_results table
    op.create_table('booking_results',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('booking_request_id', sa.String(length=36), nullable=False),
    sa.Column('pnr_number', sa.String(length=20), nullable=True),
    sa.Column('ticket_status', sa.String(length=50), nullable=True),
    sa.Column('coach_details', postgresql.JSON(astext_type=sa.Text()), nullable=True),
    sa.Column('seat_details', postgresql.JSON(astext_type=sa.Text()), nullable=True),
    sa.Column('irctc_transaction_id', sa.String(length=100), nullable=True),
    sa.Column('execution_method', sa.String(length=20), nullable=True),
    sa.Column('execution_duration_seconds', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['booking_request_id'], ['booking_requests.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('booking_request_id')
    )
    op.create_index('idx_booking_results_request', 'booking_results', ['booking_request_id'], unique=False)
    op.create_index('idx_booking_results_pnr', 'booking_results', ['pnr_number'], unique=False)

    # Create refunds table
    op.create_table('refunds',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('booking_request_id', sa.String(length=36), nullable=False),
    sa.Column('amount', sa.Float(), nullable=False),
    sa.Column('currency', sa.String(length=10), nullable=False, server_default='INR'),
    sa.Column('reason', sa.Text(), nullable=True),
    sa.Column('status', sa.String(length=20), nullable=False, server_default='PENDING'),
    sa.Column('razorpay_refund_id', sa.String(length=100), nullable=True),
    sa.Column('refund_transaction_id', sa.String(length=100), nullable=True),
    sa.Column('processed_at', sa.DateTime(), nullable=True),
    sa.Column('processed_by', sa.String(length=36), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['booking_request_id'], ['booking_requests.id'], ),
    sa.ForeignKeyConstraint(['processed_by'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_refunds_request', 'refunds', ['booking_request_id'], unique=False)
    op.create_index('idx_refunds_status', 'refunds', ['status'], unique=False)

    # Create execution_logs table
    op.create_table('execution_logs',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('booking_request_id', sa.String(length=36), nullable=False),
    sa.Column('step', sa.String(length=100), nullable=False),
    sa.Column('message', sa.Text(), nullable=False),
    sa.Column('status', sa.String(length=20), nullable=False),
    sa.Column('metadata', postgresql.JSON(astext_type=sa.Text()), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['booking_request_id'], ['booking_requests.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_execution_logs_request', 'execution_logs', ['booking_request_id'], unique=False)
    op.create_index('idx_execution_logs_status', 'execution_logs', ['status'], unique=False)
    op.create_index('idx_execution_logs_created', 'execution_logs', ['created_at'], unique=False)


def downgrade() -> None:
    """Remove booking queue system tables."""
    op.drop_index('idx_execution_logs_created', table_name='execution_logs')
    op.drop_index('idx_execution_logs_status', table_name='execution_logs')
    op.drop_index('idx_execution_logs_request', table_name='execution_logs')
    op.drop_table('execution_logs')
    
    op.drop_index('idx_refunds_status', table_name='refunds')
    op.drop_index('idx_refunds_request', table_name='refunds')
    op.drop_table('refunds')
    
    op.drop_index('idx_booking_results_pnr', table_name='booking_results')
    op.drop_index('idx_booking_results_request', table_name='booking_results')
    op.drop_table('booking_results')
    
    op.drop_index('idx_booking_queue_scheduled', table_name='booking_queue')
    op.drop_index('idx_booking_queue_priority', table_name='booking_queue')
    op.drop_index('idx_booking_queue_status', table_name='booking_queue')
    op.drop_table('booking_queue')
    
    op.drop_index('idx_request_passengers_request', table_name='booking_request_passengers')
    op.drop_table('booking_request_passengers')
    
    op.drop_index(op.f('ix_booking_requests_journey_date'), table_name='booking_requests')
    op.drop_index('idx_booking_requests_created', table_name='booking_requests')
    op.drop_index('idx_booking_requests_verification', table_name='booking_requests')
    op.drop_index('idx_booking_requests_status', table_name='booking_requests')
    op.drop_index('idx_booking_requests_user', table_name='booking_requests')
    op.drop_table('booking_requests')
