"""rename_supabase_id_to_firebase_uid

Revision ID: 7e83e709fb92
Revises: 2942391a14f9
Create Date: 2026-05-18 11:53:01.202436

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '7e83e709fb92'
down_revision: Union[str, Sequence[str], None] = '2942391a14f9'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column('supabase_id', new_column_name='firebase_uid')


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('users') as batch_op:
        batch_op.alter_column('firebase_uid', new_column_name='supabase_id')

