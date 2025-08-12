#!/usr/bin/env python3
"""
Import existing R2 photos into the database
"""
import sys
import os
sys.path.append('/usr/src/app')

import boto3
from botocore.client import Config
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.models import Photo, User
import uuid
from datetime import datetime

# R2 configuration
R2_ACCESS_KEY_ID = '4ba1fb329539b4701e02ce0e8408c00f'
R2_SECRET_ACCESS_KEY = 'f5c5936e18c57a5a8fbcb1b683da9bde12ad556ade2930d4306a783f6286e4b2'
R2_ENDPOINT_URL = 'https://fb0dc821b762ede87c5023985484491d.r2.cloudflarestorage.com'
R2_BUCKET_NAME = 'photorank-uploads'

def get_s3_client():
    return boto3.client(
        's3',
        endpoint_url=R2_ENDPOINT_URL,
        aws_access_key_id=R2_ACCESS_KEY_ID,
        aws_secret_access_key=R2_SECRET_ACCESS_KEY,
        config=Config(signature_version='s3v4'),
        region_name='auto'
    )

def get_or_create_system_user(db: Session) -> User:
    """Create a system user for orphaned photos"""
    system_user = db.query(User).filter(User.email == 'system@photorank.local').first()
    if not system_user:
        system_user = User(
            email='system@photorank.local',
            username='system',
            provider='system',
            provider_id='system_001',
            created_at=datetime.utcnow()
        )
        db.add(system_user)
        db.commit()
        db.refresh(system_user)
    return system_user

def import_r2_photos():
    """Import all existing R2 photos into the database"""
    db = SessionLocal()
    
    try:
        s3 = get_s3_client()
        
        # Get all objects from R2
        response = s3.list_objects_v2(Bucket=R2_BUCKET_NAME)
        
        if 'Contents' not in response:
            print("No files found in R2 storage")
            return
        
        system_user = get_or_create_system_user(db)
        
        imported_count = 0
        skipped_count = 0
        
        for obj in response['Contents']:
            filename = obj['Key']
            
            # Skip if already exists in database
            existing = db.query(Photo).filter(Photo.filename == filename).first()
            if existing:
                print(f"Skipping {filename} - already exists in database")
                skipped_count += 1
                continue
            
            # Create new photo record
            photo = Photo(
                filename=filename,
                elo_rating=1200.0,  # Default ELO rating
                total_duels=0,
                wins=0,
                owner_id=system_user.id,
                created_at=obj.get('LastModified', datetime.utcnow()),
                category_id=4  # Default to 'anything' category
            )
            
            db.add(photo)
            imported_count += 1
            print(f"Importing {filename}")
        
        db.commit()
        print(f"\nImport complete!")
        print(f"Imported: {imported_count} photos")
        print(f"Skipped: {skipped_count} photos")
        
    except Exception as e:
        print(f"Error importing photos: {e}")
        db.rollback()
    finally:
        db.close()

if __name__ == "__main__":
    print("🚀 Starting R2 photo import...")
    import_r2_photos()
    print("✅ Import process finished!")