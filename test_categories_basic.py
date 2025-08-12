#!/usr/bin/env python3
"""
Basic test for category functionality
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.models import Category, Photo, User
from app.database import Base

# Test database setup
DATABASE_URL = "postgresql://postgres:pepito1234@db:5432/fastapi"
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def test_categories_exist():
    """Test that categories are properly initialized"""
    db = SessionLocal()
    try:
        categories = db.query(Category).all()
        print(f"Found {len(categories)} categories:")
        for cat in categories:
            print(f"  - {cat.id}: {cat.name} ({cat.description})")
        
        expected_categories = ['paintings', 'historical-photos', 'memes', 'anything']
        actual_names = [cat.name for cat in categories]
        
        for expected in expected_categories:
            if expected not in actual_names:
                print(f"❌ Missing category: {expected}")
                return False
            else:
                print(f"✅ Found category: {expected}")
        
        return True
    finally:
        db.close()

def test_photo_has_category():
    """Test that photos have category_id"""
    db = SessionLocal()
    try:
        photos = db.query(Photo).all()
        print(f"Found {len(photos)} photos")
        
        for photo in photos:
            if photo.category_id is None:
                print(f"❌ Photo {photo.id} has no category_id")
                return False
            else:
                category = db.query(Category).filter(Category.id == photo.category_id).first()
                print(f"✅ Photo {photo.id} has category: {category.name if category else 'unknown'}")
        
        return True
    finally:
        db.close()

def test_category_foreign_key():
    """Test that category foreign key works"""
    db = SessionLocal()
    try:
        # Test that we can query photos with their categories
        photos_with_categories = db.query(Photo, Category).join(
            Category, Photo.category_id == Category.id
        ).all()
        
        print(f"Found {len(photos_with_categories)} photos with category info")
        for photo, category in photos_with_categories:
            print(f"  - Photo {photo.id}: {photo.filename} -> {category.name}")
        
        return True
    finally:
        db.close()

if __name__ == "__main__":
    print("Testing category functionality...")
    
    print("\n1. Testing categories exist...")
    if test_categories_exist():
        print("✅ Categories test passed")
    else:
        print("❌ Categories test failed")
        sys.exit(1)
    
    print("\n2. Testing photo category assignment...")
    if test_photo_has_category():
        print("✅ Photo category test passed")
    else:
        print("❌ Photo category test failed")
        sys.exit(1)
    
    print("\n3. Testing category foreign key...")
    if test_category_foreign_key():
        print("✅ Foreign key test passed")
    else:
        print("❌ Foreign key test failed")
        sys.exit(1)
    
    print("\n🎉 All category tests passed!")