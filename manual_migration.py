#!/usr/bin/env python3
"""
Manual migration script to add categories support
"""
import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Database connection using Docker environment
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:pepito1234@db:5432/fastapi")
engine = create_engine(DATABASE_URL)

def run_migration():
    with engine.connect() as conn:
        # Create categories table
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS categories (
                id SERIAL PRIMARY KEY,
                name VARCHAR NOT NULL UNIQUE,
                description VARCHAR,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            )
        """))
        
        # Insert initial categories
        conn.execute(text("""
            INSERT INTO categories (name, description) VALUES 
            ('paintings', 'Paintings and artwork'),
            ('historical-photos', 'Historical photographs'),
            ('memes', 'Internet memes and humorous content'),
            ('anything', 'Anything else')
            ON CONFLICT (name) DO NOTHING
        """))
        
        # Add category_id column to photos if it doesn't exist
        conn.execute(text("""
            ALTER TABLE photos 
            ADD COLUMN IF NOT EXISTS category_id INTEGER
        """))
        
        # Add foreign key constraint (check if constraint exists first)
        result = conn.execute(text("""
            SELECT constraint_name 
            FROM information_schema.table_constraints 
            WHERE table_name = 'photos' AND constraint_name = 'photos_category_id_fkey'
        """))
        
        if not result.fetchone():
            conn.execute(text("""
                ALTER TABLE photos 
                ADD CONSTRAINT photos_category_id_fkey 
                FOREIGN KEY (category_id) REFERENCES categories(id)
            """))
        
        # Set default category for existing photos
        conn.execute(text("""
            UPDATE photos 
            SET category_id = (SELECT id FROM categories WHERE name = 'anything')
            WHERE category_id IS NULL
        """))
        
        # Make category_id not nullable
        conn.execute(text("""
            ALTER TABLE photos 
            ALTER COLUMN category_id SET NOT NULL
        """))
        
        conn.commit()
        print("Migration completed successfully!")

if __name__ == "__main__":
    run_migration()