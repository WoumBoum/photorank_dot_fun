#!/usr/bin/env python3
"""
Script to initialize categories in the database
"""
import os
import sys
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Category
from app.database import Base

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Database connection using Docker environment
DATABASE_URL = os.getenv("DATABASE_URL", "postgresql://postgres:pepito1234@db:5432/fastapi")
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_categories():
    db = SessionLocal()
    try:
        # Check if categories already exist
        existing = db.query(Category).count()
        if existing > 0:
            print(f"Categories already initialized ({existing} found)")
            return
        
        # Create initial categories
        categories = [
            Category(name="paintings", description="Paintings and artwork"),
            Category(name="historical-photos", description="Historical photographs"),
            Category(name="memes", description="Internet memes and humorous content"),
            Category(name="anything", description="Anything else")
        ]
        
        for category in categories:
            db.add(category)
        
        db.commit()
        print("Successfully initialized categories:")
        for cat in categories:
            print(f"  - {cat.name}: {cat.description}")
            
    except Exception as e:
        print(f"Error initializing categories: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    init_categories()