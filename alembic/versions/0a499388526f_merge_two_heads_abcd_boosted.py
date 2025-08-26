"""merge two heads (abcd, boosted)

Revision ID: 0a499388526f
Revises: abcd
Create Date: 2025-08-26 14:59:13.015088

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = '0a499388526f'
down_revision = ('abcd', 'boosted_votes_on_categories')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
