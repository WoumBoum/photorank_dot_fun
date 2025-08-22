from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from ..models import User, Photo, Vote, Category
from ..schemas import UserStats, LeaderboardEntry, UsernameUpdate  # type: ignore, UsernameUpdate
from ..oauth2 import get_current_user

router = APIRouter(prefix="/users", tags=['Users'])


@router.get("/stats", response_model=UserStats)
def get_user_stats(db, current_user):
    """Get statistics for current user's photos"""
    
    print("[STATS] Getting stats for user: {} (ID: {})".format(current_user.username, current_user.id))
    
    try:
        # Get user's photos with ranking, but only include photos with valid categories
        photos = db.query(Photo).join(Category, Photo.category_id == Category.id).filter(
            Photo.owner_id == current_user.id
        ).order_by(Photo.elo_rating.desc()).all()

        print("[STATS] Found {} photos for user {}".format(len(photos), current_user.username))

        # Get global ranking for each photo
        ranked_photos = []
        for photo in photos:
            # Get rank based on ELO score
            rank_query = db.query(func.count(Photo.id)).filter(
                Photo.elo_rating > photo.elo_rating
            ).scalar() + 1

            # Get category name (should always exist due to join)
            category_name = photo.category.name if photo.category else "unknown"

            print("[STATS] Processing photo {}: {}, rank: {}, category: {}".format(photo.id, photo.filename, rank_query, category_name))

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
        
        print("[STATS] User {} has {} total votes".format(current_user.username, total_votes))
        print("[STATS] Returning {} ranked photos".format(len(ranked_photos)))
        
        return UserStats(
            photos=ranked_photos,
            total_photos=len(photos),
            total_votes=total_votes
        )
    except Exception as e:
        print("[STATS] ERROR: {}".format(str(e)))
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/me")
def get_current_user_info(current_user):
    """Get current user basic info"""
    # Determine moderator via env, consistent with categories endpoints
    import os
    is_moderator = bool(
        os.getenv("MODERATOR_PROVIDER")
        and os.getenv("MODERATOR_PROVIDER_ID")
        and current_user.provider == os.getenv("MODERATOR_PROVIDER")
        and str(current_user.provider_id) == str(os.getenv("MODERATOR_PROVIDER_ID"))
    )
    return {
        "id": current_user.id,
        "email": current_user.email,
        "username": current_user.username,
        "created_at": current_user.created_at,
        "is_moderator": is_moderator,
    }


@router.patch("/me/username")
def update_username(payload, db, current_user):
    """Update current user's pseudonym (username)."""
    # Reserved names
    reserved = {"admin", "administrator", "moderator", "support"}
    new_name = payload.username.lower()
    if new_name in reserved:
        raise HTTPException(status_code=400, detail="Username is reserved")

    # Check uniqueness
    exists = db.query(User).filter(User.username == new_name).first()
    if exists and exists.id != current_user.id:
        raise HTTPException(status_code=409, detail="Username already taken")

    current_user.username = new_name
    db.add(current_user)
    db.commit()
    db.refresh(current_user)
    return {"username": current_user.username}