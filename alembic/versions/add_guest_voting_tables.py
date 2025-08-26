"""add guest voting tables

Revision ID: add_guest_voting_tables
Revises: 00f6bcbb60fc
Create Date: 2025-01-01 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'add_guest_voting_tables'
down_revision = '00f6bcbb60fc'
branch_labels = None
depends_on = None


def upgrade():
    # Create guest_votes table
    op.create_table('guest_votes',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('winner_id', sa.Integer(), nullable=False),
        sa.Column('loser_id', sa.Integer(), nullable=False),
        sa.Column('ip_hash', sa.String(), nullable=True),
        sa.Column('user_agent_hash', sa.String(), nullable=True),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['winner_id'], ['photos.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['loser_id'], ['photos.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id')
    )
    
    # Create index on session_id for faster queries
    op.create_index('ix_guest_votes_session_id', 'guest_votes', ['session_id'])
    
    # Create guest_vote_limits table
    op.create_table('guest_vote_limits',
        sa.Column('session_id', sa.String(), nullable=False),
        sa.Column('vote_count', sa.Integer(), nullable=False, server_default='0'),
        sa.Column('last_vote_date', sa.DateTime(), server_default=sa.text('now()'), nullable=False),
        sa.Column('created_at', sa.TIMESTAMP(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.PrimaryKeyConstraint('session_id')
    )


def downgrade():
    # Drop tables in reverse order
    op.drop_table('guest_vote_limits')
    op.drop_index('ix_guest_votes_session_id', table_name='guest_votes')
    op.drop_table('guest_votes')