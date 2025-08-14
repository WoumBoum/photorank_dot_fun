from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List

from ..database import get_db
from ..models import Category, Photo, Vote, User
from ..schemas import CategoryOut, CategoryDetail, CategoryCreate
from ..oauth2 import get_current_user
from .photos import s3_client, R2_BUCKET_NAME  # reuse R2 client

router = APIRouter(prefix="/categories", tags=['Categories'])

# Helper to check site moderator via env (same as delete_category)
import os

def is_site_moderator(user: User) -> bool:
    mod_provider = os.getenv("MODERATOR_PROVIDER")
    mod_provider_id = os.getenv("MODERATOR_PROVIDER_ID")
    return bool(mod_provider and mod_provider_id and user.provider == mod_provider and str(user.provider_id) == str(mod_provider_id))


@router.get("/", response_model=List[CategoryOut])
def get_categories(db: Session = Depends(get_db)):
    """Get all available categories"""
    categories = db.query(Category).all()
    return categories


@router.post("/create", status_code=status.HTTP_201_CREATED)
def create_category(payload: CategoryCreate, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Create a new category (auth required). Names: [A-Za-z0-9_-], 2-40 chars, unique."""
    name = payload.name.strip()
    # Case-insensitive uniqueness check
    existing = db.query(Category).filter(func.lower(Category.name) == func.lower(name)).first()
    if existing:
        raise HTTPException(status_code=400, detail="Category name already exists")
    category = Category(name=name, question=payload.question.strip(), owner_id=current_user.id)
    db.add(category)
    try:
        db.commit()
    except Exception:
        db.rollback()
        # Fallback if race condition hits UNIQUE
        raise HTTPException(status_code=400, detail="Category name already exists")
    db.refresh(category)
    return {"id": category.id, "name": category.name}


@router.get("/details", response_model=List[CategoryDetail])
def get_categories_with_details(db: Session = Depends(get_db)):
    """Get all categories with aggregated data including votes and current leader"""
    
    # Subquery to get vote counts per category (divide by 2 to fix double counting)
    vote_counts = db.query(
        Photo.category_id,
        (func.count(Vote.id) / 2).label('total_votes')
    ).join(Vote, (Vote.winner_id == Photo.id) | (Vote.loser_id == Photo.id)
    ).group_by(Photo.category_id).subquery()
    
    # Subquery to get current leader per category
    leaders = db.query(
        Photo.category_id,
        Photo.filename,
        Photo.elo_rating,
        User.username.label('owner_username'),
        func.row_number().over(
            partition_by=Photo.category_id,
            order_by=Photo.elo_rating.desc()
        ).label('rank')
    ).join(User, Photo.owner_id == User.id
    ).subquery()
    
    # Main query combining all data
    categories = db.query(
        Category.id,
        Category.name,
        Category.description,
        Category.created_at,
        func.coalesce(vote_counts.c.total_votes, 0).label('raw_total_votes'),
        func.coalesce(Category.boosted_votes, 0).label('boosted_votes'),
        (func.coalesce(vote_counts.c.total_votes, 0) + func.coalesce(Category.boosted_votes, 0)).label('total_votes'),
        Category.owner_id.label('owner_id'),
        leaders.c.filename.label('current_leader_filename'),
        leaders.c.elo_rating.label('current_leader_elo'),
        leaders.c.owner_username.label('current_leader_owner')
    ).outerjoin(vote_counts, Category.id == vote_counts.c.category_id
    ).outerjoin(leaders, (Category.id == leaders.c.category_id) & (leaders.c.rank == 1)
    ).order_by((func.coalesce(vote_counts.c.total_votes, 0) + func.coalesce(Category.boosted_votes, 0)).desc(), Category.name.asc()).all()
    
    return categories


@router.post("/{category_id}/select")
def select_category(category_id: int, request: Request, db: Session = Depends(get_db)):
    """Select a category and store it in session"""
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    # Store selected category in session
    request.session["selected_category_id"] = category_id
    request.session["selected_category_name"] = category.name
    
    return {"message": f"Category '{category.name}' selected", "category_id": category_id}


@router.get("/{category_id}", response_model=CategoryOut)
def get_category(category_id: int, db: Session = Depends(get_db)):
    """Get a specific category by ID"""
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


@router.post("/select-by-name/{category_name}", status_code=status.HTTP_200_OK)
def select_category_by_name(category_name: str, request: Request, db: Session = Depends(get_db)):
    """Select a category by its name (case-insensitive) and store it in session"""
    category = db.query(Category).filter(func.lower(Category.name) == func.lower(category_name)).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    request.session["selected_category_id"] = category.id
    request.session["selected_category_name"] = category.name
    return {"message": f"Category '{category.name}' selected", "category_id": category.id}


@router.post("/{category_id}/boost-votes")
def boost_votes(category_id: int, amount: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Increase boosted_votes for a category. Allowed to category owner or site moderator."""
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    if current_user.id != (category.owner_id or -1) and not is_site_moderator(current_user):
        raise HTTPException(status_code=403, detail="Not authorized")
    if amount is None or amount == 0:
        raise HTTPException(status_code=400, detail="Amount must be non-zero")
    if amount < 0 and (category.boosted_votes or 0) + amount < 0:
        raise HTTPException(status_code=400, detail="Cannot reduce below zero")
    category.boosted_votes = (category.boosted_votes or 0) + int(amount)
    db.commit()
    return {"message": "Boost applied", "boosted_votes": category.boosted_votes, "category_id": category.id}

@router.delete("/{category_id}")
def delete_category(category_id: int, db: Session = Depends(get_db), current_user: User = Depends(get_current_user)):
    """Delete a category.
    Allowed if requester is the category owner OR a site moderator identified by stable OAuth identity.
    """
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")

    # Allow owner
    if current_user.id != category.owner_id:
        # Allow site moderator via provider/provider_id from env
        import os
        mod_provider = os.getenv("MODERATOR_PROVIDER")
        mod_provider_id = os.getenv("MODERATOR_PROVIDER_ID")
        is_moderator = bool(mod_provider and mod_provider_id and current_user.provider == mod_provider and str(current_user.provider_id) == str(mod_provider_id))
        if not is_moderator:
            raise HTTPException(status_code=403, detail="Not authorized")

    # Collect photos to remove from storage
    photos = db.query(Photo).filter(Photo.category_id == category_id).all()

    # Remove objects from R2, ignore failures
    for p in photos:
        try:
            s3_client.delete_object(Bucket=R2_BUCKET_NAME, Key=p.filename)
        except Exception as e:
            print(f"Warning: Could not delete file from R2: {e}")

    # Deleting category will cascade delete photos and votes (ondelete=CASCADE for photos; votes cascade by FK)
    db.delete(category)
    db.commit()

    return {"message": "Category deleted"}
