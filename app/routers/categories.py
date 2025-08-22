from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List

from ..database import get_db
from ..models import Category, Photo, Vote, User
from ..schemas import CategoryOut, CategoryDetail, CategoryCreate, CategoryUpdate
from ..oauth2 import get_current_user
from .photos import s3_client, R2_BUCKET_NAME  # reuse R2 client

router = APIRouter(prefix="/categories", tags=['Categories'])

# Helper to check site moderator via env (same as delete_category)
import os

def is_site_moderator(user):
    mod_provider = os.getenv("MODERATOR_PROVIDER")
    mod_provider_id = os.getenv("MODERATOR_PROVIDER_ID")
    return bool(mod_provider and mod_provider_id and user.provider == mod_provider and str(user.provider_id) == str(mod_provider_id))


@router.get("/", response_model=List[CategoryOut])
def get_categories(db):
    """Get all available categories"""
    categories = db.query(Category).all()
    return categories


@router.post("/create", status_code=status.HTTP_201_CREATED)
def create_category(payload, db, current_user):
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
def get_categories_with_details(db):
    """Get all categories with aggregated data including votes and current leader"""

    # Get all categories with their basic info
    categories = db.query(Category).all()

    result = []
    for category in categories:
        # Get vote count for this category (only from photos that have valid categories)
        vote_count = db.query(func.count(Vote.id)).select_from(
            Vote.join(Photo, (Vote.winner_id == Photo.id) | (Vote.loser_id == Photo.id))
        ).filter(Photo.category_id == category.id).scalar() or 0

        # Get the current leader for this category
        leader_query = db.query(
            Photo.filename,
            Photo.elo_rating,
            User.username.label('owner_username')
        ).join(User, Photo.owner_id == User.id
        ).filter(Photo.category_id == category.id
        ).order_by(Photo.elo_rating.desc()).first()

        # Create a dictionary that matches the CategoryDetail schema
        # Use the same structure but ensure proper types
        category_dict = {
            "id": category.id,
            "name": category.name,
            "description": category.description,
            "created_at": category.created_at,
            "total_votes": int((vote_count / 2) + (category.boosted_votes or 0)),
            "owner_id": category.owner_id,
            "current_leader_filename": leader_query.filename if leader_query else None,
            "current_leader_elo": float(leader_query.elo_rating) if leader_query and leader_query.elo_rating else None,
            "current_leader_owner": leader_query.owner_username if leader_query else None
        }

        result.append(category_dict)

    # Sort by total votes descending, then by name
    result.sort(key=lambda x: (-x['total_votes'], x['name']))

    return result


@router.post("/{category_id}/select")
def select_category(category_id, request, db):
    """Select a category and store it in session"""
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    
    # Store selected category in session
    request.session["selected_category_id"] = category_id
    request.session["selected_category_name"] = category.name
    
    return {"message": "Category '{}' selected".format(category.name), "category_id": category_id}


@router.get("/{category_id}", response_model=CategoryOut)
def get_category(category_id, db):
    """Get a specific category by ID"""
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    return category


@router.post("/select-by-name/{category_name}", status_code=status.HTTP_200_OK)
def select_category_by_name(category_name, request, db):
    """Select a category by its name (case-insensitive) and store it in session"""
    category = db.query(Category).filter(func.lower(Category.name) == func.lower(category_name)).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    request.session["selected_category_id"] = category.id
    request.session["selected_category_name"] = category.name
    return {"message": "Category '{}' selected".format(category.name), "category_id": category.id}


@router.post("/{category_id}/boost-votes")
def boost_votes(category_id, amount, db, current_user):
    """Increase boosted_votes for a category. Allowed ONLY to site moderator."""
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    if not is_site_moderator(current_user):
        raise HTTPException(status_code=403, detail="Not authorized")
    if amount is None or amount == 0:
        raise HTTPException(status_code=400, detail="Amount must be non-zero")
    if amount < 0 and (category.boosted_votes or 0) + amount < 0:
        raise HTTPException(status_code=400, detail="Cannot reduce below zero")
    category.boosted_votes = (category.boosted_votes or 0) + int(amount)
    db.commit()
    return {"message": "Boost applied", "boosted_votes": category.boosted_votes, "category_id": category.id}

@router.patch("/{category_id}")
def update_category(category_id, payload, db, current_user):
    """Update category name/question/description. Only site moderator allowed."""
    category = db.query(Category).filter(Category.id == category_id).first()
    if not category:
        raise HTTPException(status_code=404, detail="Category not found")
    if not is_site_moderator(current_user):
        raise HTTPException(status_code=403, detail="Not authorized")

    changed = False
    if payload.name is not None:
        new_name = payload.name.strip()
        # Check case-insensitive uniqueness
        exists = db.query(Category).filter(func.lower(Category.name) == func.lower(new_name), Category.id != category_id).first()
        if exists:
            raise HTTPException(status_code=400, detail="Category name already exists")
        category.name = new_name
        changed = True
    if payload.question is not None:
        category.question = payload.question.strip()
        changed = True
    if payload.description is not None:
        category.description = payload.description.strip() if payload.description else None
        changed = True
    if changed:
        db.commit()
        db.refresh(category)
    return {"id": category.id, "name": category.name, "question": category.question, "description": category.description}


@router.delete("/{category_id}")
def delete_category(category_id, db, current_user):
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
            print("Warning: Could not delete file from R2: {}".format(e))

    # Explicitly delete photos first to ensure they're removed before category deletion
    for photo in photos:
        db.delete(photo)

    # Deleting category will cascade delete any remaining photos and votes (ondelete=CASCADE for photos; votes cascade by FK)
    db.delete(category)
    db.commit()

    return {"message": "Category deleted"}



