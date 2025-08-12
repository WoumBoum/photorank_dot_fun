from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from ..models import User, Photo, Vote, Category
from ..schemas import UserStats, LeaderboardEntry
from ..oauth2 import get_current_user

router = APIRouter(prefix="/users", tags=['Users'])


@router.get("/stats", response_model=UserStats)
def get_user_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get statistics for current user's photos"""
    
    print(f"[STATS] Getting stats for user: {current_user.username} (ID: {current_user.id})")
    
    try:
        # Get user's photos with ranking
        photos = db.query(Photo).filter(
            Photo.owner_id == current_user.id
        ).order_by(Photo.elo_rating.desc()).all()
        
        print(f"[STATS] Found {len(photos)} photos for user {current_user.username}")
        
        # Get global ranking for each photo
        ranked_photos = []
        for photo in photos:
            # Get rank based on ELO score
            rank_query = db.query(func.count(Photo.id)).filter(
                Photo.elo_rating > photo.elo_rating
            ).scalar() + 1
            
            # Get category name
            category = db.query(Category).filter(Category.id == photo.category_id).first()
            category_name = category.name if category else "unknown"
            
            print(f"[STATS] Processing photo {photo.id}: {photo.filename}, rank: {rank_query}, category: {category_name}")
            
            ranked_photos.append(LeaderboardEntry(
                id=photo.id,
                filename=photo.filename,
                elo_rating=photo.elo_rating,
                total_duels=photo.total_duels,
                wins=photo.wins,
                owner_username=current_user.username,
                rank=rank_query,
                category_name=category_name
            ))
        
        # Get total votes by user
        total_votes = db.query(Vote).filter(
            Vote.user_id == current_user.id
        ).count()
        
        print(f"[STATS] User {current_user.username} has {total_votes} total votes")
        print(f"[STATS] Returning {len(ranked_photos)} ranked photos")
        
        return UserStats(
            photos=ranked_photos,
            total_photos=len(photos),
            total_votes=total_votes
        )
    except Exception as e:
        print(f"[STATS] ERROR: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/me")
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user basic info"""
    return {
        "id": current_user.id,
        "email": current_user.email,
        "username": current_user.username,
        "created_at": current_user.created_at
    }