"""merge heads

Revision ID: ddbbc1ddcf58
Revises: add_categories, d75f1d243572, elo_ranking_system
Create Date: 2025-07-16 21:46:45.168993

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'ddbbc1ddcf58'
down_revision = ('add_categories', 'd75f1d243572', 'elo_ranking_system')
branch_labels = None
depends_on = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
