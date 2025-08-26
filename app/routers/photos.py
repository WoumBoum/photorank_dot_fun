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
import csv
import io
import httpx

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
    credentials = Depends(security),
    db = Depends(get_db)
):
    """Get current user if authenticated, otherwise return None"""
    if credentials is None:
        return None

    token = credentials.credentials
    try:
        payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
        user_id = payload.get("user_id")
        if user_id is None:
            return None
    except JWTError:
        return None

    user = db.query(User).filter(User.id == user_id).first()
    return user


def is_admin_user(user):
    """Check if the current user is an admin based on environment variables"""
    mod_provider = os.getenv("MODERATOR_PROVIDER")
    mod_provider_id = os.getenv("MODERATOR_PROVIDER_ID")
    return bool(
        mod_provider and mod_provider_id
        and user.provider == mod_provider
        and str(user.provider_id) == str(mod_provider_id)
    )

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
    
    # Calculate total possible pairs (n choose 2)
    total_possible_pairs = len(all_photos) * (len(all_photos) - 1) // 2
    
    # For authenticated users, exclude already voted pairs
    voted_pairs_count = 0
    progress_percentage = 0.0
    voted_pairs = set()
    next_top5_pairs = None
    
    if current_user:
        # Get all votes by this user in this category
        user_votes = db.query(Vote).join(Photo, (Vote.winner_id == Photo.id) | (Vote.loser_id == Photo.id))\
            .filter(Photo.category_id == selected_category_id, Vote.user_id == current_user.id).all()
        
        # Calculate actual remaining Top 5 matches
        next_top5_pairs = None
        if len(all_photos) >= 5:
            # Get current rankings for all photos in category
            ranked_photos = db.query(Photo).filter(
                Photo.category_id == selected_category_id
            ).order_by(Photo.elo_rating.desc()).all()
            
            # Get top 5 photo IDs
            top5_photos = [p.id for p in ranked_photos[:5]]
            
            # Calculate all possible Top 5 pairs (n choose 2 for top 5 photos)
            total_top5_pairs = len(top5_photos) * (len(top5_photos) - 1) // 2
            
            # Count already voted Top 5 pairs
            voted_top5_pairs = 0
            for vote in user_votes:
                if vote.winner_id in top5_photos and vote.loser_id in top5_photos:
                    voted_top5_pairs += 1
            
            # Calculate remaining Top 5 pairs
            remaining_top5_pairs = total_top5_pairs - voted_top5_pairs
            next_top5_pairs = remaining_top5_pairs if remaining_top5_pairs > 0 else None
        
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
    
    # Calculate progress
    if current_user:
        voted_pairs_count = len(voted_pairs)
        progress_percentage = (voted_pairs_count / total_possible_pairs) * 100 if total_possible_pairs > 0 else 0
    else:
        voted_pairs_count = 0
        progress_percentage = 0.0
    
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
    
    # Detect if this is an important match (Top 5 or Top 10)
    is_top_match = None
    if current_user and photos and len(photos) == 2:
        # Get current rankings for all photos in category
        ranked_photos = db.query(Photo).filter(
            Photo.category_id == selected_category_id
        ).order_by(Photo.elo_rating.desc()).all()
        
        # Find ranks of the current photos
        photo1_rank = next((i+1 for i, p in enumerate(ranked_photos) if p.id == photos[0].id), None)
        photo2_rank = next((i+1 for i, p in enumerate(ranked_photos) if p.id == photos[1].id), None)
        
        if photo1_rank and photo2_rank:
            if photo1_rank <= 5 and photo2_rank <= 5:
                is_top_match = "TOP_5"
    
    # Add progress info for authenticated users
    if current_user:
        return PhotoPair(
            photos=result,
            progress=f"{voted_pairs_count}/{total_possible_pairs}",
            progress_percentage=progress_percentage,
            next_top5_pairs=next_top5_pairs,
            is_top_match=is_top_match
        )
    else:
        return PhotoPair(photos=result)


@router.get("/leaderboard", response_model=List[LeaderboardEntry])
def get_leaderboard(
    limit: int = Query(100, ge=0, le=1000, description="Maximum number of results to return"),
    category_id: int = Query(None, description="Filter by category ID"),
    db: Session = Depends(get_db)
):
    """Get top photos ranked by ELO"""
    query = db.query(Photo).filter(Photo.total_duels >= 0)
    
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
        .filter(Photo.category_id == category.id, Photo.total_duels >= 0)
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
        Photo.total_duels >= 0,
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








@router.post("/upload/session", response_model=PhotoOut)
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


@router.post("/upload/session/batch", response_model=List[PhotoOut])
async def upload_photos_session_batch(
    request: Request,
    files: List[UploadFile] = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Upload up to 10 photos using session category"""
    selected_category_id = request.session.get("selected_category_id")
    if not selected_category_id:
        raise HTTPException(status_code=400, detail="No category selected")

    if not files or len(files) == 0:
        raise HTTPException(status_code=400, detail="No files provided")
    if len(files) > 10:
        raise HTTPException(status_code=400, detail="Batch size exceeds limit of 10")

    for f in files:
        if not f.content_type or not f.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="All files must be images")

    # Rate limit cumulative
    from ..models import UploadLimit
    today = datetime.utcnow().date()
    upload_limit = db.query(UploadLimit).filter(UploadLimit.user_id == current_user.id).first()

    if upload_limit:
        if upload_limit.last_upload_date == today:
            if upload_limit.upload_count + len(files) > 50000:  # do not change threshold
                raise HTTPException(status_code=429, detail="Daily upload limit reached (5 photos/day)")
            upload_limit.upload_count += len(files)
        else:
            upload_limit.upload_count = len(files)
            upload_limit.last_upload_date = datetime.utcnow()
    else:
        upload_limit = UploadLimit(
            user_id=current_user.id,
            upload_count=len(files),
            last_upload_date=datetime.utcnow()
        )
        db.add(upload_limit)

    category = db.query(Category).filter(Category.id == selected_category_id).first()
    if not category:
        raise HTTPException(status_code=400, detail="Invalid category")

    created_photos: List[Photo] = []
    try:
        for f in files:
            file_extension = Path(f.filename).suffix
            filename = f"{uuid.uuid4()}{file_extension}"
            content = await f.read()
            s3_client.put_object(
                Bucket=R2_BUCKET_NAME,
                Key=filename,
                Body=content,
                ContentType=f.content_type
            )

            photo = Photo(
                filename=filename,
                owner_id=current_user.id,
                category_id=selected_category_id
            )
            db.add(photo)
            created_photos.append(photo)
        db.commit()
        for p in created_photos:
            db.refresh(p)
    except Exception:
        db.rollback()
        raise HTTPException(status_code=500, detail="Failed to upload batch")

    return [
        PhotoOut(
            id=p.id,
            filename=p.filename,
            elo_rating=p.elo_rating,
            total_duels=p.total_duels,
            wins=p.wins,
            created_at=p.created_at,
            owner_id=p.owner_id,
            owner_username=current_user.username,
            category_id=p.category_id,
            category_name=category.name
        )
        for p in created_photos
    ]


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


@router.patch("/{photo_id}/elo")
async def set_photo_elo(
    photo_id: int,
    elo: float = Query(..., gt=0, lt=4000, description="New ELO rating"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Moderator-only: Set a photo's ELO rating directly."""
    import os
    is_moderator = bool(
        os.getenv("MODERATOR_PROVIDER")
        and os.getenv("MODERATOR_PROVIDER_ID")
        and current_user.provider == os.getenv("MODERATOR_PROVIDER")
        and str(current_user.provider_id) == str(os.getenv("MODERATOR_PROVIDER_ID"))
    )
    if not is_moderator:
        raise HTTPException(status_code=403, detail="Moderator access required")

    photo = db.query(Photo).filter(Photo.id == photo_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")

    photo.elo_rating = float(elo)
    db.add(photo)
    db.commit()
    db.refresh(photo)
    return {"id": photo.id, "elo_rating": photo.elo_rating}


@router.delete("/{photo_id}")
async def delete_photo(
    photo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a photo: allowed for owner or site moderator."""
    import os
    mod_provider = os.getenv("MODERATOR_PROVIDER")
    mod_provider_id = os.getenv("MODERATOR_PROVIDER_ID")
    def is_site_moderator(user: User) -> bool:
        return bool(mod_provider and mod_provider_id and user.provider == mod_provider and str(user.provider_id) == str(mod_provider_id))

    photo = db.query(Photo).filter(Photo.id == photo_id).first()
    
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found")
    
    if photo.owner_id != current_user.id and not is_site_moderator(current_user):
        raise HTTPException(status_code=403, detail="Not authorized to delete this photo")
    
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



@router.delete("/categories/{category_id}/photos/{photo_id}")
async def delete_photo_as_category_owner(
    category_id: int,
    photo_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Category owner or site moderator can delete any photo in the category."""
    import os
    mod_provider = os.getenv("MODERATOR_PROVIDER")
    mod_provider_id = os.getenv("MODERATOR_PROVIDER_ID")
    def is_site_moderator(user: User) -> bool:
        return bool(mod_provider and mod_provider_id and user.provider == mod_provider and str(user.provider_id) == str(mod_provider_id))

    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    if category.owner_id != current_user.id and not is_site_moderator(current_user):
        raise HTTPException(status_code=403, detail="Not authorized to moderate this category")

    photo = db.query(Photo).filter(Photo.id == photo_id, Photo.category_id == category_id).first()
    if not photo:
        raise HTTPException(status_code=404, detail="Photo not found in this category")

    # Delete the file from R2 storage
    try:
        s3_client.delete_object(Bucket=R2_BUCKET_NAME, Key=photo.filename)
    except Exception as e:
        print(f"Warning: Could not delete file from R2: {e}")

    # Delete associated votes
    db.query(Vote).filter(
        (Vote.winner_id == photo_id) | (Vote.loser_id == photo_id)
    ).delete()

    db.delete(photo)
    db.commit()

    return {"message": "Photo deleted successfully"}


@router.post("/upload/admin/batch", response_model=List[PhotoOut])
async def upload_photos_admin_batch(
    request: Request,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Admin-only: Upload photos from CSV with custom ELO ratings"""
    # Check if user is admin
    if not is_admin_user(current_user):
        raise HTTPException(status_code=403, detail="Admin access required")

    selected_category_id = request.session.get("selected_category_id")
    if not selected_category_id:
        raise HTTPException(status_code=400, detail="No category selected")

    # Validate file type
    if not file.filename.endswith('.csv'):
        raise HTTPException(status_code=400, detail="File must be a CSV file")

    # Read and parse CSV
    content = await file.read()
    content_str = content.decode('utf-8')
    csv_reader = csv.DictReader(io.StringIO(content_str))

    # Validate CSV headers
    required_headers = {'image_url', 'elo', 'user_id'}
    if not required_headers.issubset(set(csv_reader.fieldnames or [])):
        raise HTTPException(
            status_code=400,
            detail="CSV must contain 'image_url', 'elo', and 'user_id' columns"
        )

    # Parse and validate rows
    photos_to_create = []
    for row_num, row in enumerate(csv_reader, start=2):  # Start at 2 to account for header
        image_url = row.get('image_url', '').strip()
        elo_str = row.get('elo', '').strip()
        user_id_str = row.get('user_id', '').strip()

        if not image_url:
            raise HTTPException(
                status_code=400,
                detail=f"Row {row_num}: image_url cannot be empty"
            )

        try:
            elo = float(elo_str)
            if elo < 0 or elo > 4000:
                raise ValueError("ELO must be between 0 and 4000")
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Row {row_num}: Invalid ELO rating '{elo_str}'"
            )

        try:
            user_id = int(user_id_str)
            if user_id <= 0:
                raise ValueError("User ID must be positive")
        except ValueError:
            raise HTTPException(
                status_code=400,
                detail=f"Row {row_num}: Invalid user ID '{user_id_str}'"
            )

        photos_to_create.append({'image_url': image_url, 'elo': elo, 'user_id': user_id})

    if not photos_to_create:
        raise HTTPException(status_code=400, detail="No valid photos found in CSV")

    # Validate category
    category = db.query(Category).filter(Category.id == selected_category_id).first()
    if not category:
        raise HTTPException(status_code=400, detail="Invalid category")

    created_photos = []
    try:
        for photo_data in photos_to_create:
            # Download image from URL
            try:
                async with httpx.AsyncClient(timeout=30.0) as client:
                    response = await client.get(photo_data['image_url'])
                    response.raise_for_status()
                    image_content = response.content
                    content_type = response.headers.get('content-type', 'image/jpeg')

                if not content_type.startswith('image/'):
                    raise HTTPException(
                        status_code=400,
                        detail=f"URL {photo_data['image_url']} does not point to an image"
                    )
            except httpx.RequestError as e:
                raise HTTPException(
                    status_code=400,
                    detail=f"Failed to download image from {photo_data['image_url']}: {str(e)}"
                )

            # Generate unique filename
            file_extension = Path(photo_data['image_url']).suffix or '.jpg'
            filename = f"{uuid.uuid4()}{file_extension}"

            # Upload to R2
            s3_client.put_object(
                Bucket=R2_BUCKET_NAME,
                Key=filename,
                Body=image_content,
                ContentType=content_type
            )

            # Create photo record with custom ELO and specified user
            photo = Photo(
                filename=filename,
                owner_id=photo_data['user_id'],
                category_id=selected_category_id,
                elo_rating=photo_data['elo']
            )
            db.add(photo)
            created_photos.append(photo)

        db.commit()
        for p in created_photos:
            db.refresh(p)

    except Exception as e:
        db.rollback()
        raise HTTPException(status_code=500, detail=f"Failed to upload photos: {str(e)}")

    return [
        PhotoOut(
            id=p.id,
            filename=p.filename,
            elo_rating=p.elo_rating,
            total_duels=p.total_duels,
            wins=p.wins,
            created_at=p.created_at,
            owner_id=p.owner_id,
            owner_username=current_user.username,
            category_id=p.category_id,
            category_name=category.name
        )
        for p in created_photos
    ]
