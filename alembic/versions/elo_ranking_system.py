"""elo ranking system - complete redesign

Revision ID: elo_ranking_system
Revises: d7a3a262e1b8
Create Date: 2025-07-14 18:50:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'elo_ranking_system'
down_revision = 'd7a3a262e1b8'
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Drop existing tables with dependencies
    op.execute('DROP TABLE IF EXISTS votes CASCADE')
    op.execute('DROP TABLE IF EXISTS posts CASCADE')
    op.execute('DROP TABLE IF EXISTS users CASCADE')
    
    # Create new users table for OAuth
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('username', sa.String(), nullable=False),
        sa.Column('provider', sa.String(), nullable=False),
        sa.Column('provider_id', sa.String(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email'),
        sa.UniqueConstraint('username'),
        sa.UniqueConstraint('provider_id')
    )
    
    # Create photos table
    op.create_table('photos',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('filename', sa.String(), nullable=False),
        sa.Column('elo_rating', sa.Float(), nullable=False, server_default='1200.0'),
        sa.Column('total_duels', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('wins', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('owner_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('filename')
    )
    
    # Create votes table for Elo system
    op.create_table('votes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('winner_id', sa.Integer(), nullable=False),
        sa.Column('loser_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['winner_id'], ['photos.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['loser_id'], ['photos.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create upload limits table
    op.create_table('upload_limits',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('upload_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_upload_date', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id')
    )


def downgrade() -> None:
    # Drop all tables
    op.execute('DROP TABLE IF EXISTS upload_limits CASCADE')
    op.execute('DROP TABLE IF EXISTS votes CASCADE')
    op.execute('DROP TABLE IF EXISTS photos CASCADE')
    op.execute('DROP TABLE IF EXISTS users CASCADE')
    
    # Recreate original tables
    op.create_table('users',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('email', sa.String(), nullable=False),
        sa.Column('password', sa.String(), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('email')
    )
    
    op.create_table('posts',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('title', sa.String(), nullable=False),
        sa.Column('content', sa.String(), nullable=False),
        sa.Column('published', sa.Boolean(), server_default='TRUE', nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('owner_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['owner_id'], ['users.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    op.create_table('votes',
        sa.Column('user_id', sa.Integer(), nullable=False),
        sa.Column('post_id', sa.Integer(), nullable=False),
        sa.ForeignKeyConstraint(['user_id'], ['users.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['post_id'], ['posts.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('user_id', 'post_id')
    )