#!/usr/bin/env python3
"""
Comprehensive database setup script for PhotoRank
Creates all necessary tables and default data for the application
"""

import os
import sys
from sqlalchemy import create_engine, text
from sqlalchemy.exc import SQLAlchemyError
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Database connection
DATABASE_URL = os.getenv("DATABASE_URL")
if not DATABASE_URL:
    # Construct from environment variables
    DATABASE_HOSTNAME = os.getenv("DATABASE_HOSTNAME", "localhost")
    DATABASE_PORT = os.getenv("DATABASE_PORT", "5432")
    DATABASE_USERNAME = os.getenv("DATABASE_USERNAME", "postgres")
    DATABASE_PASSWORD = os.getenv("DATABASE_PASSWORD", "")
    DATABASE_NAME = os.getenv("DATABASE_NAME", "postgres")
    
    DATABASE_URL = f"postgresql://{DATABASE_USERNAME}:{DATABASE_PASSWORD}@{DATABASE_HOSTNAME}:{DATABASE_PORT}/{DATABASE_NAME}"

def create_tables():
    """Create all necessary tables for PhotoRank"""
    engine = create_engine(DATABASE_URL)
    
    try:
        with engine.connect() as conn:
            # Create tables in correct order to handle foreign key dependencies
            
            # Create users table
            logger.info("Creating users table...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS users (
                    id SERIAL PRIMARY KEY,
                    email VARCHAR(255) UNIQUE NOT NULL,
                    username VARCHAR(255) UNIQUE NOT NULL,
                    provider VARCHAR(50) NOT NULL,
                    provider_id VARCHAR(255) NOT NULL,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
                    UNIQUE(provider, provider_id)
                )
            """))
            
            # Create categories table
            logger.info("Creating categories table...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS categories (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(100) UNIQUE NOT NULL,
                    description TEXT,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """))
            
            # Create photos table
            logger.info("Creating photos table...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS photos (
                    id SERIAL PRIMARY KEY,
                    filename VARCHAR(255) NOT NULL,
                    elo_rating NUMERIC DEFAULT 1200,
                    total_duels INTEGER DEFAULT 0,
                    wins INTEGER DEFAULT 0,
                    category_id INTEGER REFERENCES categories(id) ON DELETE SET NULL,
                    owner_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """))
            
            # Create votes table
            logger.info("Creating votes table...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS votes (
                    id SERIAL PRIMARY KEY,
                    user_id INTEGER REFERENCES users(id) ON DELETE CASCADE,
                    winner_id INTEGER REFERENCES photos(id) ON DELETE CASCADE,
                    loser_id INTEGER REFERENCES photos(id) ON DELETE CASCADE,
                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                )
            """))
            
            # Create upload_limits table
            logger.info("Creating upload_limits table...")
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS upload_limits (
                    user_id INTEGER PRIMARY KEY REFERENCES users(id) ON DELETE CASCADE,
                    upload_count INTEGER DEFAULT 0,
                    last_upload_date DATE DEFAULT CURRENT_DATE
                )
            """))
            
            # Create indexes for better performance
            logger.info("Creating indexes...")
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_photos_owner ON photos(owner_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_photos_category ON photos(category_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_votes_user ON votes(user_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_votes_winner ON votes(winner_id)"))
            conn.execute(text("CREATE INDEX IF NOT EXISTS idx_votes_loser ON votes(loser_id)"))
            
            conn.commit()
            logger.info("All tables created successfully!")
            
    except SQLAlchemyError as e:
        logger.error(f"Error creating tables: {e}")
        raise

def insert_default_categories():
    """Insert default categories if they don't exist"""
    engine = create_engine(DATABASE_URL)
    
    try:
        with engine.connect() as conn:
            # Check if categories already exist
            result = conn.execute(text("SELECT COUNT(*) FROM categories"))
            count = result.scalar()
            
            if count == 0:
                logger.info("Inserting default categories...")
                conn.execute(text("""
                    INSERT INTO categories (name, description) VALUES
                    ('Nature', 'Landscapes, wildlife, and natural scenes'),
                    ('Urban', 'Cityscapes, architecture, and street photography'),
                    ('People', 'Portraits, candid shots, and human moments'),
                    ('Abstract', 'Artistic, experimental, and conceptual photography')
                """))
                conn.commit()
                logger.info("Default categories inserted successfully!")
            else:
                logger.info("Categories already exist, skipping insertion")
                
    except SQLAlchemyError as e:
        logger.error(f"Error inserting categories: {e}")
        raise

def verify_setup():
    """Verify that all tables were created correctly"""
    engine = create_engine(DATABASE_URL)
    
    try:
        with engine.connect() as conn:
            tables = ['users', 'categories', 'photos', 'votes', 'upload_limits']
            
            for table in tables:
                result = conn.execute(text(f"SELECT COUNT(*) FROM {table}"))
                count = result.scalar()
                logger.info(f"Table {table}: {count} rows")
                
            # Check categories
            result = conn.execute(text("SELECT name FROM categories ORDER BY id"))
            categories = [row[0] for row in result]
            logger.info(f"Categories: {categories}")
            
    except SQLAlchemyError as e:
        logger.error(f"Error verifying setup: {e}")
        raise

if __name__ == "__main__":
    logger.info("Starting database setup...")
    logger.info(f"Database URL: {DATABASE_URL.split('@')[-1] if '@' in DATABASE_URL else 'localhost'}")
    
    try:
        create_tables()
        insert_default_categories()
        verify_setup()
        logger.info("Database setup completed successfully!")
        sys.exit(0)
    except Exception as e:
        logger.error(f"Database setup failed: {e}")
        sys.exit(1)