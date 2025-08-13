"""add question and owner to categories

Revision ID: abcd
Revises: dd bbc1ddcf58_merge_heads
Create Date: 2025-08-13
"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.sql import table, column
from sqlalchemy import Integer, String, Text

# revision identifiers, used by Alembic.
revision = 'abcd'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    # Add columns (nullable at first for backfill)
    op.add_column('categories', sa.Column('question', sa.Text(), nullable=True))
    op.add_column('categories', sa.Column('owner_id', sa.Integer(), nullable=True))
    # Try to backfill owner anon user
    conn = op.get_bind()
    # Ensure anon user exists
    res = conn.execute(sa.text("SELECT id FROM users WHERE username=:u"), {"u": "anon3164144616"}).fetchone()
    if not res:
        # Create pseudo anon user with random provider_id
        conn.execute(sa.text("""
        INSERT INTO users (email, username, provider, provider_id)
        VALUES (:email, :username, 'anon', 'anon-3164144616')
        ON CONFLICT (username) DO NOTHING
        """), {"email": "anon3164144616@example.com", "username": "anon3164144616"})
        res = conn.execute(sa.text("SELECT id FROM users WHERE username=:u"), {"u": "anon3164144616"}).fetchone()
    anon_id = res[0]
    # Backfill question and owner for existing categories
    rows = conn.execute(sa.text("SELECT id, name FROM categories")).fetchall()
    for cid, name in rows:
        q = f"What is the best {name}?"
        conn.execute(sa.text("UPDATE categories SET question=:q, owner_id=:oid WHERE id=:cid"), {"q": q, "oid": anon_id, "cid": cid})
    # Now set non-null constraint
    op.alter_column('categories', 'question', existing_type=sa.Text(), nullable=False)
    # Add FK for owner_id
    op.create_foreign_key('categories_owner_id_fkey', 'categories', 'users', ['owner_id'], ['id'])


def downgrade():
    op.drop_constraint('categories_owner_id_fkey', 'categories', type_='foreignkey')
    op.drop_column('categories', 'owner_id')
    op.drop_column('categories', 'question')
