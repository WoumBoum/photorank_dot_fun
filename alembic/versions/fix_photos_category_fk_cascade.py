"""Fix photos.category_id foreign key to include CASCADE on delete

Revision ID: fix_photos_category_fk_cascade
Revises: abcd
Create Date: 2025-01-22

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'fix_photos_category_fk_cascade'
down_revision = 'abcd'
branch_labels = None
depends_on = None


def upgrade():
    # Drop the existing foreign key constraint
    op.drop_constraint('photos_category_id_fkey', 'photos', type_='foreignkey')

    # Create a new foreign key constraint with CASCADE on delete
    op.create_foreign_key(
        'photos_category_id_fkey',
        'photos',
        'categories',
        ['category_id'],
        ['id'],
        ondelete='CASCADE'
    )


def downgrade():
    # Drop the CASCADE foreign key constraint
    op.drop_constraint('photos_category_id_fkey', 'photos', type_='foreignkey')

    # Recreate the original foreign key constraint without CASCADE
    op.create_foreign_key(
        'photos_category_id_fkey',
        'photos',
        'categories',
        ['category_id'],
        ['id']
    )