"""Empty baseline for existing schema

Revision ID: 41af9fd39336
Revises: 
Create Date: 2026-02-14 06:23:33.150853

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
import geoalchemy2


# revision identifiers, used by Alembic.
revision: str = '41af9fd39336'
down_revision: Union[str, Sequence[str], None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # ### commands copied from autogen migration (initial app schema)
    op.create_table('routes',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('source', sa.String(length=255), nullable=False),
    sa.Column('destination', sa.String(length=255), nullable=False),
    sa.Column('segments', sa.JSON(), nullable=False),
    sa.Column('total_duration', sa.String(length=50), nullable=False),
    sa.Column('total_cost', sa.Float(), nullable=False),
    sa.Column('budget_category', sa.String(length=50), nullable=False),
    sa.Column('num_transfers', sa.Integer(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_routes_created_at'), 'routes', ['created_at'], unique=False)
    op.create_index(op.f('ix_routes_destination'), 'routes', ['destination'], unique=False)
    op.create_index(op.f('ix_routes_source'), 'routes', ['source'], unique=False)

    op.create_table('stations',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('name', sa.String(length=255), nullable=False),
    sa.Column('city', sa.String(length=255), nullable=False),
    sa.Column('latitude', sa.Float(), nullable=False),
    sa.Column('longitude', sa.Float(), nullable=False),
    sa.Column('geom', geoalchemy2.types.Geometry(geometry_type='POINT', srid=4326, from_text='ST_GeomFromEWKT', name='geometry'), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index('idx_stations_geom', 'stations', ['geom'], unique=False, postgresql_using='gist')
    op.create_index(op.f('ix_stations_city'), 'stations', ['city'], unique=False)
    op.create_index(op.f('ix_stations_name'), 'stations', ['name'], unique=False)

    op.create_table('stations_master',
    sa.Column('station_code', sa.String(length=10), nullable=False),
    sa.Column('station_name', sa.String(length=255), nullable=False),
    sa.Column('city', sa.String(length=255), nullable=False),
    sa.Column('state', sa.String(length=255), nullable=False),
    sa.Column('is_junction', sa.Boolean(), nullable=True),
    sa.Column('latitude', sa.Float(), nullable=True),
    sa.Column('longitude', sa.Float(), nullable=True),
    sa.Column('geo_hash', sa.String(length=12), nullable=True),
    sa.PrimaryKeyConstraint('station_code')
    )
    op.create_index(op.f('ix_stations_master_city'), 'stations_master', ['city'], unique=False)
    op.create_index(op.f('ix_stations_master_station_name'), 'stations_master', ['station_name'], unique=False)

    op.create_table('users',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('email', sa.String(length=255), nullable=False),
    sa.Column('password_hash', sa.String(length=255), nullable=False),
    sa.Column('phone_number', sa.String(length=20), nullable=True),
    sa.Column('role', sa.String(length=50), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_users_email'), 'users', ['email'], unique=True)
    op.create_index(op.f('ix_users_role'), 'users', ['role'], unique=False)

    op.create_table('vehicles',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('vehicle_number', sa.String(length=50), nullable=False),
    sa.Column('type', sa.String(length=50), nullable=False),
    sa.Column('operator', sa.String(length=255), nullable=False),
    sa.Column('capacity', sa.Integer(), nullable=True),
    sa.CheckConstraint("type IN ('train', 'bus', 'flight')", name='vehicle_type_check'),
    sa.PrimaryKeyConstraint('id')
    )

    op.create_table('bookings',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('route_id', sa.String(length=36), nullable=False),
    sa.Column('travel_date', sa.String(length=10), nullable=False),
    sa.Column('payment_status', sa.String(length=50), nullable=True),
    sa.Column('amount_paid', sa.Float(), nullable=True),
    sa.Column('booking_details', sa.JSON(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['route_id'], ['routes.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_bookings_created_at'), 'bookings', ['created_at'], unique=False)
    op.create_index(op.f('ix_bookings_user_id'), 'bookings', ['user_id'], unique=False)

    op.create_table('segments',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('source_station_id', sa.String(length=36), nullable=False),
    sa.Column('dest_station_id', sa.String(length=36), nullable=False),
    sa.Column('vehicle_id', sa.String(length=36), nullable=True),
    sa.Column('transport_mode', sa.String(length=50), nullable=False),
    sa.Column('departure_time', sa.String(length=8), nullable=False),
    sa.Column('arrival_time', sa.String(length=8), nullable=False),
    sa.Column('duration_minutes', sa.Integer(), nullable=False),
    sa.Column('distance_km', sa.Float(), nullable=True),
    sa.Column('arrival_day_offset', sa.Integer(), nullable=True),
    sa.Column('cost', sa.Float(), nullable=False),
    sa.Column('operating_days', sa.String(length=7), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['dest_station_id'], ['stations.id'], ),
    sa.ForeignKeyConstraint(['source_station_id'], ['stations.id'], ),
    sa.ForeignKeyConstraint(['vehicle_id'], ['vehicles.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_segments_dest_station_id'), 'segments', ['dest_station_id'], unique=False)
    op.create_index(op.f('ix_segments_source_station_id'), 'segments', ['source_station_id'], unique=False)
    op.create_index(op.f('ix_segments_vehicle_id'), 'segments', ['vehicle_id'], unique=False)

    op.create_table('payments',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('booking_id', sa.String(length=36), nullable=True),
    sa.Column('razorpay_order_id', sa.String(length=255), nullable=True),
    sa.Column('razorpay_payment_id', sa.String(length=255), nullable=True),
    sa.Column('status', sa.String(length=50), nullable=True),
    sa.Column('amount', sa.Float(), nullable=False),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.Column('updated_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['booking_id'], ['bookings.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_payments_booking_id'), 'payments', ['booking_id'], unique=False)
    op.create_index(op.f('ix_payments_razorpay_order_id'), 'payments', ['razorpay_order_id'], unique=False)
    op.create_index(op.f('ix_payments_razorpay_payment_id'), 'payments', ['razorpay_payment_id'], unique=False)

    op.create_table('reviews',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('booking_id', sa.String(length=36), nullable=False),
    sa.Column('rating', sa.Integer(), nullable=False),
    sa.Column('comment', sa.Text(), nullable=True),
    sa.Column('created_at', sa.DateTime(), nullable=True),
    sa.CheckConstraint('rating >= 1 AND rating <= 5', name='review_rating_check'),
    sa.ForeignKeyConstraint(['booking_id'], ['bookings.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_reviews_booking_id'), 'reviews', ['booking_id'], unique=True)
    op.create_index(op.f('ix_reviews_user_id'), 'reviews', ['user_id'], unique=False)

    op.create_table('unlocked_routes',
    sa.Column('id', sa.String(length=36), nullable=False),
    sa.Column('user_id', sa.String(length=36), nullable=False),
    sa.Column('route_id', sa.String(length=36), nullable=False),
    sa.Column('payment_id', sa.String(length=36), nullable=True),
    sa.Column('unlocked_at', sa.DateTime(), nullable=True),
    sa.ForeignKeyConstraint(['payment_id'], ['payments.id'], ),
    sa.ForeignKeyConstraint(['route_id'], ['routes.id'], ),
    sa.ForeignKeyConstraint(['user_id'], ['users.id'], ),
    sa.PrimaryKeyConstraint('id')
    )
    op.create_index(op.f('ix_unlocked_routes_payment_id'), 'unlocked_routes', ['payment_id'], unique=False)
    op.create_index(op.f('ix_unlocked_routes_route_id'), 'unlocked_routes', ['route_id'], unique=False)
    op.create_index(op.f('ix_unlocked_routes_user_id'), 'unlocked_routes', ['user_id'], unique=False)
    # ### end Alembic commands ###


def downgrade() -> None:
    """Downgrade schema."""
    # drop dependents first
    op.drop_index(op.f('ix_unlocked_routes_payment_id'), table_name='unlocked_routes')
    op.drop_index(op.f('ix_unlocked_routes_route_id'), table_name='unlocked_routes')
    op.drop_index(op.f('ix_unlocked_routes_user_id'), table_name='unlocked_routes')
    op.drop_table('unlocked_routes')

    op.drop_index(op.f('ix_reviews_booking_id'), table_name='reviews')
    op.drop_index(op.f('ix_reviews_user_id'), table_name='reviews')
    op.drop_table('reviews')

    op.drop_index(op.f('ix_payments_booking_id'), table_name='payments')
    op.drop_index(op.f('ix_payments_razorpay_order_id'), table_name='payments')
    op.drop_index(op.f('ix_payments_razorpay_payment_id'), table_name='payments')
    op.drop_table('payments')

    op.drop_index(op.f('ix_segments_dest_station_id'), table_name='segments')
    op.drop_index(op.f('ix_segments_source_station_id'), table_name='segments')
    op.drop_index(op.f('ix_segments_vehicle_id'), table_name='segments')
    op.drop_table('segments')

    op.drop_index(op.f('ix_bookings_created_at'), table_name='bookings')
    op.drop_index(op.f('ix_bookings_user_id'), table_name='bookings')
    op.drop_table('bookings')

    op.drop_table('vehicles')

    op.drop_index(op.f('ix_users_email'), table_name='users')
    op.drop_index(op.f('ix_users_role'), table_name='users')
    op.drop_table('users')

    op.drop_index(op.f('ix_stations_master_city'), table_name='stations_master')
    op.drop_index(op.f('ix_stations_master_station_name'), table_name='stations_master')
    op.drop_table('stations_master')

    op.drop_index(op.f('idx_stations_geom'), table_name='stations', postgresql_using='gist')
    op.drop_index(op.f('ix_stations_city'), table_name='stations')
    op.drop_index(op.f('ix_stations_name'), table_name='stations')
    op.drop_table('stations')

    op.drop_index(op.f('ix_routes_created_at'), table_name='routes')
    op.drop_index(op.f('ix_routes_destination'), table_name='routes')
    op.drop_index(op.f('ix_routes_source'), table_name='routes')
    op.drop_table('routes')
    # ### end Alembic commands ###
