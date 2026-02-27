"""Add Supabase profiles, risk_zones and live_locations

Revision ID: 20260226_supabase
Revises: ff2a3b4c5d6_add_station_departures_index
Create Date: 2026-02-26 12:00:00.000000
"""
from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = '20260226_supabase'
down_revision = 'ff2a3b4c5d6_add_station_departures_index'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # profiles table mirrors auth.users from Supabase
    op.create_table(
        'profiles',
        sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
        sa.Column('name', sa.String(length=255), nullable=True),
        sa.Column('phone', sa.String(length=50), nullable=True),
        sa.Column('gender', sa.String(length=50), nullable=True),
        sa.Column('emergency_contact', sa.String(length=255), nullable=True),
        sa.Column('created_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['id'], ['auth.users.id'], name='fk_profiles_user')
    )

    # risk zones for safety scoring
    op.create_table(
        'risk_zones',
        sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
        sa.Column('latitude', sa.Numeric(), nullable=False),
        sa.Column('longitude', sa.Numeric(), nullable=False),
        sa.Column('risk_level', sa.Integer(), nullable=False),
        sa.Column('description', sa.Text(), nullable=True),
    )

    # live_locations for realtime tracking
    op.create_table(
        'live_locations',
        sa.Column('id', sa.String(length=36), primary_key=True, nullable=False),
        sa.Column('user_id', sa.String(length=36), nullable=False),
        sa.Column('latitude', sa.Numeric(), nullable=False),
        sa.Column('longitude', sa.Numeric(), nullable=False),
        sa.Column('speed', sa.Numeric(), nullable=True),
        sa.Column('updated_at', sa.DateTime(), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id']),
    )

    # trigger function to create profile row when a new auth.user is inserted
    op.execute("""
    create function public.handle_new_user()
    returns trigger as $$
    begin
      insert into public.profiles (id)
      values (new.id);
      return new;
    end;
    $$ language plpgsql;

    create trigger on_auth_user_created
    after insert on auth.users
    for each row execute procedure public.handle_new_user();
    """
    )


def downgrade() -> None:
    # drop triggers and function first
    op.execute("""drop trigger if exists on_auth_user_created on auth.users;
                 drop function if exists public.handle_new_user();""")

    op.drop_table('live_locations')
    op.drop_table('risk_zones')
    op.drop_table('profiles')
