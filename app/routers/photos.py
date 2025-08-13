from fastapi import APIRouter, Depends, HTTPException, UploadFile, File, Form, Query, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
import os
import uuid
from pathlib import Path
from datetime import datetime
import boto3
from botocore.client import Config
from dotenv import load_dotenv

from fastapi import APIRouter, Depends, HTTPException, Request, Query

from ..database import get_db
from ..models import Photo, User, Vote, UploadLimit, Category
from ..schemas import PhotoOut, PhotoCreate, PhotoPair, LeaderboardEntry
from ..oauth2 import get_current_user
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from jose import JWTError, jwt
from ..config import settings

security = HTTPBearer(auto_error=False)

def get_current_user_optional(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Get current user if authenticated, otherwise return None"""
    if credentials is None:
        return None
    
    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id: int = payload.get("user_id")
        if user_id is None:
            return None
    except JWTError:
        return None
    
    user = db.query(User).filter(User.id == user_id).first()
    return user

router = APIRouter(prefix="/photos", tags=['Photos'])

load_dotenv()

# Cloudflare R2 Configuration
R2_ACCESS_KEY_ID = os.getenv("R2_ACCESS_KEY_ID")
R2_SECRET_ACCESS_KEY = os.getenv("R2_SECRET_ACCESS_KEY")
R2_ENDPOINT_URL = os.getenv("R2_ENDPOINT_URL")
R2_PUBLIC_URL = os.getenv("R2_PUBLIC_URL")
R2_BUCKET_NAME = os.getenv("R2_BUCKET_NAME")

# Upload directory for local storage (for tests)
UPLOAD_DIR = Path("app/static/uploads")

# Initialize S3 client for R2
s3_client = boto3.client(
    's3',
    endpoint_url=R2_ENDPOINT_URL,
    aws_access_key_id=R2_ACCESS_KEY_ID,
    aws_secret_access_key=R2_SECRET_ACCESS_KEY,
    config=Config(signature_version='s3v4'),
    region_name='auto'
)


@router.get("/pair", response_model=PhotoPair)
def get_photo_pair(
    category_id: int = Query(None, description="Filter by category ID"),
    db: Session = Depends(get_db)
):
    """Get two random photos for voting"""
    query = db.query(Photo)
    
    if category_id:
        query = query.filter(Photo.category_id == category_id)
    
    photos = query.order_by(func.random()).limit(2).all()
    
    if len(photos) < 2:
        raise HTTPException(status_code=404, detail="Not enough photos")
    
    # Add owner username and category info to each photo
    result = []
    for photo in photos:
        owner = db.query(User).filter(User.id == photo.owner_id).first()
        category = db.query(Category).filter(Category.id == photo.category_id).first()
        photo_out = PhotoOut(
            id=photo.id,
            filename=photo.filename,
            elo_rating=photo.elo_rating,
            total_duels=photo.total_duels,
            wins=photo.wins,
            created_at=photo.created_at,
            owner_id=photo.owner_id,
            owner_username=owner.username,
            category_id=photo.category_id,
            category_name=category.name if category else "unknown"
        )
        result.append(photo_out)
    
    return PhotoPair(photos=result)


@router.get("/pair/session", response_model=PhotoPair)
def get_photo_pair_session(
    request: Request,
    db: Session = Depends(get_db),
    current_user: Optional[User] = Depends(get_current_user_optional)
):
    """Get two random photos for voting using session-based category, excluding already voted pairs"""
    selected_category_id = request.session.get("selected_category_id")
    
    if not selected_category_id:
        raise HTTPException(status_code=400, detail="No category selected")
    
    # Get all photos in the category
    all_photos = db.query(Photo).filter(Photo.category_id == selected_category_id).all()
    
    if len(all_photos) < 2:
        raise HTTPException(status_code=404, detail="Not enough photos in selected category")
    
    # For authenticated users, exclude already voted pairs
    if current_user:
        # Get all votes by this user in this category
        user_votes = db.query(Vote).join(Photo, (Vote.winner_id == Photo.id) | (Vote.loser_id == Photo.id))\
            .filter(Photo.category_id == selected_category_id, Vote.user_id == current_user.id).all()
        
        # Create set of already voted pairs (as sorted tuples to handle bidirectional votes)
        voted_pairs = set()
        for vote in user_votes:
            pair = tuple(sorted([vote.winner_id, vote.loser_id]))
            voted_pairs.add(pair)
        
        # Find all possible photo pairs that haven't been voted on
        available_pairs = []
        photo_ids = [photo.id for photo in all_photos]
        
        for i in range(len(photo_ids)):
            for j in range(i + 1, len(photo_ids)):
                pair = tuple(sorted([photo_ids[i], photo_ids[j]]))
                if pair not in voted_pairs:
                    available_pairs.append(pair)
        
        # Debug logging
        print(f"DEBUG: User {current_user.id} has {len(user_votes)} votes in category {selected_category_id}")
        print(f"DEBUG: Total photos: {len(all_photos)}, Voted pairs: {len(voted_pairs)}, Available pairs: {len(available_pairs)}")
        
        if not available_pairs:
            raise HTTPException(status_code=410, detail="No more photo pairs to vote on in this category")
        
        # Randomly select one of the available pairs
        import random
        selected_pair = random.choice(available_pairs)
        photos = [db.query(Photo).filter(Photo.id == selected_pair[0]).first(),
                 db.query(Photo).filter(Photo.id == selected_pair[1]).first()]
    else:
        # For unauthenticated users, just return random pairs
        import random
        photos = random.sample(all_photos, 2)
    
    # Add owner username and category info to each photo
    result = []
    for photo in photos:
        owner = db.query(User).filter(User.id == photo.owner_id).first()
        category = db.query(Category).filter(Category.id == photo.category_id).first()
        photo_out = PhotoOut(
            id=photo.id,
            filename=photo.filename,
            elo_rating=photo.elo_rating,
            total_duels=photo.total_duels,
            wins=photo.wins,
            created_at=photo.created_at,
            owner_id=photo.owner_id,
            owner_username=owner.username,
            category_id=photo.category_id,
            category_name=category.name if category else "unknown"
        )
        result.append(photo_out)
    
    return PhotoPair(photos=result)


@router.get("/leaderboard", response_model=List[LeaderboardEntry])
def get_leaderboard(
    limit: int = Query(100, ge=0, le=1000, description="Maximum number of results to return"),
    category_id: int = Query(None, description="Filter by category ID"),
    db: Session = Depends(get_db)
):
    """Get top photos ranked by ELO"""
    query = db.query(Photo).filter(Photo.total_duels >= 5)
    
    if category_id:
        query = query.filter(Photo.category_id == category_id)
    
    query = query.order_by(Photo.elo_rating.desc())
    
    if limit > 0:
        query = query.limit(limit)
    
    photos = query.all()
    
    result = []
    for rank, photo in enumerate(photos, 1):
        owner = db.query(User).filter(User.id == photo.owner_id).first()
        category = db.query(Category).filter(Category.id == photo.category_id).first()
        result.append(LeaderboardEntry(
            id=photo.id,
            filename=photo.filename,
            elo_rating=photo.elo_rating,
            total_duels=photo.total_duels,
            wins=photo.wins,
            owner_username=owner.username if owner else "unknown",
            rank=rank,
            category_name=category.name if category else "unknown"
        ))
    
    return result


@router.get("/leaderboard/{category_name}", response_model=List[LeaderboardEntry])
def get_leaderboard_by_category(category_name: str, limit: int = Query(100, ge=0, le=1000), db: Session = Depends(get_db)):
    """Leaderboard for a specific category by name (case-insensitive)."""
    category = db.query(Category).filter(func.lower(Category.name) == func.lower(category_name)).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    query = (
        db.query(Photo)
        .filter(Photo.category_id == category.id, Photo.total_duels >= 5)
        .order_by(Photo.elo_rating.desc())
    )
    if limit > 0:
        query = query.limit(limit)

    photos = query.all()
    result = []
    for rank, photo in enumerate(photos, 1):
        owner = db.query(User).filter(User.id == photo.owner_id).first()
        result.append(LeaderboardEntry(
            id=photo.id,
            filename=photo.filename,
            elo_rating=photo.elo_rating,
            total_duels=photo.total_duels,
            wins=photo.wins,
            owner_username=owner.username if owner else "unknown",
            rank=rank,
            category_name=category.name
        ))
    return result


@router.get("/leaderboard/session", response_model=List[LeaderboardEntry])
def get_leaderboard_session(
    request: Request,
    limit: int = Query(100, ge=0, le=1000, description="Maximum number of results to return"),
    db: Session = Depends(get_db)
):
    """Get top photos ranked by ELO for the selected category in session"""
    selected_category_id = request.session.get("selected_category_id")
    
    if not selected_category_id:
        raise HTTPException(status_code=400, detail="No category selected")
    
    query = db.query(Photo).filter(
        Photo.total_duels >= 1,
        Photo.category_id == selected_category_id
    )
    
    query = query.order_by(Photo.elo_rating.desc())
    
    if limit > 0:
        query = query.limit(limit)
    
    photos = query.all()
    
    result = []
    for rank, photo in enumerate(photos, 1):
        owner = db.query(User).filter(User.id == photo.owner_id).first()
        category = db.query(Category).filter(Category.id == photo.category_id).first()
        result.append(LeaderboardEntry(
            id=photo.id,
            filename=photo.filename,
            elo_rating=photo.elo_rating,
            total_duels=photo.total_duels,
            wins=photo.wins,
            owner_username=owner.username if owner else "unknown",
            rank=rank,
            category_name=category.name if category else "unknown"
        ))
    
    return result


from fastapi import File, UploadFile, Form
from . import __init__ as _dummy
from ..turnstile import require_turnstile

@router.post("/upload", response_model=PhotoOut, dependencies=[Depends(require_turnstile)])
async def upload_photo(
    file: UploadFile = File(...),
    category_id: int = Form(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload a new photo"""
    # Check file type
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # Check upload limit
    from ..models import UploadLimit
    today = datetime.utcnow().date()
    upload_limit = db.query(UploadLimit).filter(
        UploadLimit.user_id == current_user.id
    ).first()
    
    if upload_limit:
        if upload_limit.last_upload_date == today:
            if upload_limit.upload_count >= 50000: #please don't change I keep it like that for debugging
                raise HTTPException(
                    status_code=429, 
                    detail="Daily upload limit reached (5 photos/day)"
                )
            upload_limit.upload_count += 1
        else:
            upload_limit.upload_count = 1
            upload_limit.last_upload_date = datetime.utcnow()
    else:
        upload_limit = UploadLimit(
            user_id=current_user.id,
            upload_count=1,
            last_upload_date=datetime.utcnow()
        )
        db.add(upload_limit)
    
    # Generate unique filename
    file_extension = Path(file.filename).suffix
    filename = f"{uuid.uuid4()}{file_extension}"
    
    # Upload to R2
    content = await file.read()
    s3_client.put_object(
        Bucket=R2_BUCKET_NAME,
        Key=filename,
        Body=content,
        ContentType=file.content_type
    )
    
    # Validate category
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=400, detail="Invalid category")
    
    # Create photo record
    photo = Photo(
        filename=filename,
        owner_id=current_user.id,
        category_id=category_id
    )
    db.add(photo)
    db.commit()
    db.refresh(photo)
    
    return PhotoOut(
        id=photo.id,
        filename=photo.filename,
        elo_rating=photo.elo_rating,
        total_duels=photo.total_duels,
        wins=photo.wins,
        created_at=photo.created_at,
        owner_id=photo.owner_id,
        owner_username=current_user.username,
        category_id=photo.category_id,
        category_name=category.name
    )


@router.post("/upload/session", response_model=PhotoOut, dependencies=[Depends(require_turnstile)])
async def upload_photo_session(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload a new photo using session-based category"""
    selected_category_id = request.session.get("selected_category_id")
    
    if not selected_category_id:
        raise HTTPException(status_code=400, detail="No category selected")
    
    # Check file type
    if not file.content_type.startswith('image/'):
        raise HTTPException(status_code=400, detail="File must be an image")
    
    # Check upload limit
    from ..models import UploadLimit
    today = datetime.utcnow().date()
    upload_limit = db.query(UploadLimit).filter(
        UploadLimit.user_id == current_user.id
    ).first()
    
    if upload_limit:
        if upload_limit.last_upload_date == today:
            if upload_limit.upload_count >= 50000: #please don't change I keep it like that for debugging
                raise HTTPException(
                    status_code=429, 
                    detail="Daily upload limit reached (5 photos/day)"
                )
            upload_limit.upload_count += 1
        else:
            upload_limit.upload_count = 1
            upload_limit.last_upload_date = datetime.utcnow()
    else:
        upload_limit = UploadLimit(
            user_id=current_user.id,
            upload_count=1,
            last_upload_date=datetime.utcnow()
        )
        db.add(upload_limit)
    
    # Generate unique filename
    file_extension = Path(file.filename).suffix
    filename = f"{uuid.uuid4()}{file_extension}"
    
    # Upload to R2
    content = await file.read()
    s3_client.put_object(
        Bucket=R2_BUCKET_NAME,
        Key=filename,
        Body=content,
        ContentType=file.content_type
    )
    
    # Validate category
    category = db.query(Category).filter(Category.id == selected_category_id).first()
    if not category:
        raise HTTPException(status_code=400, detail="Invalid category")
    
    # Create photo record
    photo = Photo(
        filename=filename,
        owner_id=current_user.id,
        category_id=selected_category_id
    )
    db.add(photo)
    db.commit()
    db.refresh(photo)
    
    return PhotoOut(
        id=photo.id,
        filename=photo.filename,
        elo_rating=photo.elo_rating,
        total_duels=photo.total_duels,
        wins=photo.wins,
        created_at=photo.created_at,
        owner_id=photo.owner_id,
        owner_username=current_user.username,
        category_id=photo.category_id,
        category_name=category.name
    )


@router.get("/{filename}")
async def get_photo(filename: str):
    """Serve photo from appropriate storage"""
    # First check local storage for existing photos
    local_path = Path("app/static/uploads") / filename
    if local_path.exists():
        from fastapi.responses import FileResponse
        return FileResponse(local_path)
    
    # Then check R2 storage and serve directly
    try:
        response = s3_client.get_object(Bucket=R2_BUCKET_NAME, Key=filename)
        content = response['Body'].read()
        content_type = response.get('ContentType', 'image/jpeg')
        
        from fastapi.responses import Response
        return Response(
            content=content,
            media_type=content_type,
            headers={
                "Access-Control-Allow-Origin": "*",
                "Cache-Control": "public, max-age=3600"
            }
        )
    except s3_client.exceptions.NoSuchKey:
        raise HTTPException(status_code=404, detail="Photo not found")
    except Exception as e:
        # Fallback to local storage
        if local_path.exists():
            from fastapi.responses import FileResponse
            return FileResponse(local_path)
        raise HTTPException(status_code=404, detail="Photo not found")


@router.delete("/{photo_id}")
async def delete_photo(
    photo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a user's own photo"""
    photo = db.query(Photo).filter(Photo.id == photo_id).first()
    
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    
    if photo.owner_id != current_user.id:
        raise HTTPException(
            status_code=403, 
            detail="You can only delete your own photos"
        )
    
    # Delete the file from R2 storage
    try:
        s3_client.delete_object(Bucket=R2_BUCKET_NAME, Key=photo.filename)
    except Exception as e:
        # Log error but don't fail the deletion
        print(f"Warning: Could not delete file from R2: {e}")
    
    # Delete associated votes
    db.query(Vote).filter(
        (Vote.winner_id == photo_id) | (Vote.loser_id == photo_id)
    ).delete()
    
    # Delete the photo record
    db.delete(photo)
    db.commit()
    
    return {"message": "Photo deleted successfully"}