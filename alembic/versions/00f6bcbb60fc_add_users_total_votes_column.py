"""add users.total_votes column

Revision ID: 00f6bcbb60fc
Revises: 0a499388526f
Create Date: 2025-08-26 14:59:27.041000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '00f6bcbb60fc'
down_revision = '0a499388526f'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column('users', sa.Column('total_votes', sa.Integer(), nullable=False, server_default='0'))
    # Drop the server default after backfill so future inserts rely on app defaults if desired
    op.alter_column('users', 'total_votes', server_default=None)


def downgrade() -> None:
    op.drop_column('users', 'total_votes')
