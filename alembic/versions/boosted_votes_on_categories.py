from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision = 'boosted_votes_on_categories'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Add boosted_votes with default 0
    op.add_column('categories', sa.Column('boosted_votes', sa.Integer(), nullable=False, server_default='0'))
    # Remove server_default after setting initial value
    op.alter_column('categories', 'boosted_votes', server_default=None)

def downgrade():
    op.drop_column('categories', 'boosted_votes')
