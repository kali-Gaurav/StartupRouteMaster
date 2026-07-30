"""Add seat inventory and booking models

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-16 13:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6a7'
down_revision: Union[str, Sequence[str], None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""

    # Create coaches table
    op.create_table('coaches',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('train_id', sa.Integer(), nullable=False),
    sa.Column('coach_number', sa.String(length=10), nullable=False),
    sa.Column('coach_class', sa.Enum('SL', 'AC3', 'AC2', 'AC1', 'CC', 'EC', 'EA', name='coachclass'), nullable=False),
    sa.Column('total_seats', sa.Integer(), nullable=False),
    sa.Column('base_fare_multiplier', sa.Float(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['train_id'], ['trips.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('train_id', 'coach_number', name='uq_train_coach')
    )
    op.create_index(op.f('ix_coaches_train_id'), 'coaches', ['train_id'], unique=False)

    # Create seats table
    op.create_table('seats',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('coach_id', sa.String(length=36), nullable=False),
    sa.Column('seat_number', sa.String(length=10), nullable=False),
    sa.Column('seat_type', sa.Enum('LOWER', 'MIDDLE', 'UPPER', 'SIDE_LOWER', 'SIDE_UPPER', 'WINDOW', 'AISLE', name='seattype'), nullable=False),
    sa.Column('is_active', sa.Boolean(), nullable=False),
    sa.Column('is_preferred', sa.Boolean(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['coach_id'], ['coaches.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('coach_id', 'seat_number', name='uq_coach_seat')
    )
    op.create_index(op.f('ix_seats_coach_id'), 'seats', ['coach_id'], unique=False)

    # Create seat_inventory table
    op.create_table('seat_inventory',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('trip_id', sa.Integer(), nullable=False),
    sa.Column('segment_from_stop_id', sa.Integer(), nullable=False),
    sa.Column('segment_to_stop_id', sa.Integer(), nullable=False),
    sa.Column('date', sa.Date(), nullable=False),
    sa.Column('quota_type', sa.Enum('GENERAL', 'TATKAL', 'LADIES', 'SENIOR_CITIZEN', 'DEFENCE', 'FOREIGN_TOURIST', 'DUTY_PASS', 'PARLIAMENT', 'HANDICAPPED', 'YUVA', name='quotatype'), nullable=False),
    sa.Column('total_seats', sa.Integer(), nullable=False),
    sa.Column('available_seats', sa.Integer(), nullable=False),
    sa.Column('booked_seats', sa.Integer(), nullable=False),
    sa.Column('blocked_seats', sa.Integer(), nullable=False),
    sa.Column('current_waitlist_position', sa.Integer(), nullable=False),
    sa.Column('rac_count', sa.Integer(), nullable=False),
    sa.Column('last_updated', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['segment_from_stop_id'], ['stops.id'], ),
    sa.ForeignKeyConstraint(['segment_to_stop_id'], ['stops.id'], ),
    sa.ForeignKeyConstraint(['trip_id'], ['trips.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('trip_id', 'segment_from_stop_id', 'segment_to_stop_id', 'date', 'quota_type', name='uq_inventory_segment')
    )
    op.create_index(op.f('ix_seat_inventory_quota'), 'seat_inventory', ['quota_type'], unique=False)
    op.create_index(op.f('ix_seat_inventory_segment'), 'seat_inventory', ['segment_from_stop_id', 'segment_to_stop_id'], unique=False)
    op.create_index(op.f('ix_seat_inventory_trip_date'), 'seat_inventory', ['trip_id', 'date'], unique=False)

    # Create quota_inventory table
    op.create_table('quota_inventory',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('inventory_id', sa.String(length=36), nullable=False),
    sa.Column('quota_type', sa.Enum('GENERAL', 'TATKAL', 'LADIES', 'SENIOR_CITIZEN', 'DEFENCE', 'FOREIGN_TOURIST', 'DUTY_PASS', 'PARLIAMENT', 'HANDICAPPED', 'YUVA', name='quotatype'), nullable=False),
    sa.Column('allocated_seats', sa.Integer(), nullable=False),
    sa.Column('available_seats', sa.Integer(), nullable=False),
    sa.Column('max_allocation', sa.Integer(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['inventory_id'], ['seat_inventory.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('inventory_id', 'quota_type', name='uq_quota_inventory')
    )
    op.create_index(op.f('ix_quota_inventory_inventory'), 'quota_inventory', ['inventory_id'], unique=False)

    # Create waitlist_queue table
    op.create_table('waitlist_queue',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('inventory_id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('waitlist_position', sa.Integer(), nullable=False),
    sa.Column('booking_request_time', sa.DateTime(), nullable=False),
    sa.Column('passengers_json', sa.JSON(), nullable=False),
    sa.Column('preferences_json', sa.JSON(), nullable=True),
    sa.Column('status', sa.Enum('CONFIRMED', 'RAC', 'WAITLIST', 'CANCELLED', name='bookingstatus'), nullable=False),
    sa.Column('promoted_at', sa.DateTime(), nullable=True),
    sa.Column('expired_at', sa.DateTime(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['inventory_id'], ['seat_inventory.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_waitlist_queue_inventory'), 'waitlist_queue', ['inventory_id'], unique=False)
    op.create_index(op.f('ix_waitlist_queue_position'), 'waitlist_queue', ['waitlist_position'], unique=False)
    op.create_index(op.f('ix_waitlist_queue_user'), 'waitlist_queue', ['user_id'], unique=False)

    # Create pnr_records table
    op.create_table('pnr_records',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('pnr_number', sa.String(length=10), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('travel_date', sa.Date(), nullable=False),
    sa.Column('total_passengers', sa.Integer(), nullable=False),
    sa.Column('total_fare', sa.Numeric(precision=10, scale=2), nullable=False),
    sa.Column('booking_status', sa.Enum('CONFIRMED', 'RAC', 'WAITLIST', 'CANCELLED', name='bookingstatus'), nullable=False),
    sa.Column('payment_status', sa.String(length=20), nullable=False),
    sa.Column('payment_id', sa.String(length=100), nullable=True),
    sa.Column('segments_json', sa.JSON(), nullable=False),
    sa.Column('cancelled_at', sa.DateTime(), nullable=True),
    sa.Column('refund_amount', sa.Numeric(precision=10, scale=2), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('pnr_number', name='uq_pnr_number')
    )
    op.create_index(op.f('ix_pnr_records_date'), 'pnr_records', ['travel_date'], unique=False)
    op.create_index(op.f('ix_pnr_records_pnr'), 'pnr_records', ['pnr_number'], unique=False)
    op.create_index(op.f('ix_pnr_records_user'), 'pnr_records', ['user_id'], unique=False)

    # Create passenger_details table
    op.create_table('passenger_details',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('pnr_id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=100), nullable=False),
    sa.Column('age', sa.Integer(), nullable=False),
    sa.Column('gender', sa.String(length=10), nullable=False),
    sa.Column('berth_preference', sa.Enum('LOWER', 'MIDDLE', 'UPPER', 'SIDE_LOWER', 'SIDE_UPPER', 'WINDOW', 'AISLE', name='seattype'), nullable=True),
    sa.Column('coach_number', sa.String(length=10), nullable=True),
    sa.Column('seat_number', sa.String(length=10), nullable=True),
    sa.Column('seat_type', sa.Enum('LOWER', 'MIDDLE', 'UPPER', 'SIDE_LOWER', 'SIDE_UPPER', 'WINDOW', 'AISLE', name='seattype'), nullable=True),
    sa.Column('status', sa.Enum('CONFIRMED', 'RAC', 'WAITLIST', 'CANCELLED', name='bookingstatus'), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['pnr_id'], ['pnr_records.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_passenger_details_pnr'), 'passenger_details', ['pnr_id'], unique=False)

    # Create booking_locks table
    op.create_table('booking_locks',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('lock_key', sa.String(length=200), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('session_id', sa.String(length=100), nullable=False),
    sa.Column('acquired_at', sa.DateTime(), nullable=False),
    sa.Column('expires_at', sa.DateTime(), nullable=False),
    sa.Column('ttl_seconds', sa.Integer(), nullable=False),
    sa.Column('lock_type', sa.String(length=20), nullable=False),
    sa.Column('resource_id', sa.String(length=100), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id'),
    sa.UniqueConstraint('lock_key', name='uq_lock_key')
    )
    op.create_index(op.f('ix_booking_locks_expiry'), 'booking_locks', ['expires_at'], unique=False)
    op.create_index(op.f('ix_booking_locks_key'), 'booking_locks', ['lock_key'], unique=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_index(op.f('ix_booking_locks_key'), table_name='booking_locks')
    op.drop_index(op.f('ix_booking_locks_expiry'), table_name='booking_locks')
    op.drop_table('booking_locks')
    op.drop_index(op.f('ix_passenger_details_pnr'), table_name='passenger_details')
    op.drop_table('passenger_details')
    op.drop_index(op.f('ix_pnr_records_user'), table_name='pnr_records')
    op.drop_index(op.f('ix_pnr_records_pnr'), table_name='pnr_records')
    op.drop_index(op.f('ix_pnr_records_date'), table_name='pnr_records')
    op.drop_table('pnr_records')
    op.drop_index(op.f('ix_waitlist_queue_user'), table_name='waitlist_queue')
    op.drop_index(op.f('ix_waitlist_queue_position'), table_name='waitlist_queue')
    op.drop_index(op.f('ix_waitlist_queue_inventory'), table_name='waitlist_queue')
    op.drop_table('waitlist_queue')
    op.drop_index(op.f('ix_quota_inventory_inventory'), table_name='quota_inventory')
    op.drop_table('quota_inventory')
    op.drop_index(op.f('ix_seat_inventory_trip_date'), table_name='seat_inventory')
    op.drop_index(op.f('ix_seat_inventory_segment'), table_name='seat_inventory')
    op.drop_index(op.f('ix_seat_inventory_quota'), table_name='seat_inventory')
    op.drop_table('seat_inventory')
    op.drop_index(op.f('ix_seats_coach_id'), table_name='seats')
    op.drop_table('seats')
    op.drop_index(op.f('ix_coaches_train_id'), table_name='coaches')
    op.drop_table('coaches')
