"""add categories table and category_id to photos

Revision ID: add_categories
Revises: 
Create Date: 2025-07-16 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_categories'
down_revision = None
branch_labels = None
depends_on = None


def upgrade():
    # Create categories table
    op.create_table('categories',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(), nullable=False, unique=True),
        sa.Column('description', sa.String(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Insert initial categories
    op.execute("""
        INSERT INTO categories (name, description) VALUES 
        ('paintings', 'Paintings and artwork'),
        ('historical-photos', 'Historical photographs'),
        ('memes', 'Internet memes and humorous content'),
        ('anything', 'Anything else')
    """)
    
    # Add category_id column to photos
    op.add_column('photos', sa.Column('category_id', sa.Integer(), nullable=True))
    op.create_foreign_key('photos_category_id_fkey', 'photos', 'categories', ['category_id'], ['id'])
    
    # Set all existing photos to 'anything' category
    op.execute("""
        UPDATE photos SET category_id = (SELECT id FROM categories WHERE name = 'anything')
    """)
    
    # Make category_id not nullable
    op.alter_column('photos', 'category_id', nullable=False)


def downgrade():
    op.drop_constraint('photos_category_id_fkey', 'photos', type_='foreignkey')
    op.drop_column('photos', 'category_id')
    op.drop_table('categories')