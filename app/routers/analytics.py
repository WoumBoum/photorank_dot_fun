from datetime import datetime, timedelta
from typing import Dict
import os

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from ..models import User, Photo, Vote
from ..oauth2 import get_current_user

router = APIRouter(prefix="/analytics", tags=["Analytics"])

templates = Jinja2Templates(directory="app/templates")


def require_moderator(current_user: User = Depends(get_current_user)) -> User:
    mod_provider = os.getenv("MODERATOR_PROVIDER")
    mod_id = os.getenv("MODERATOR_PROVIDER_ID")
    if not (mod_provider and mod_id):
        # If not configured, deny by default
        raise HTTPException(status_code=403, detail="Moderator access not configured")
    if current_user.provider == mod_provider and str(current_user.provider_id) == str(mod_id):
        return current_user
    raise HTTPException(status_code=403, detail="Moderator access required")


@router.get("/", response_class=HTMLResponse)
def analytics_page(request: Request, _: User = Depends(require_moderator)):
    return templates.TemplateResponse("analytics.html", {"request": request})


@router.get("/overview")
def analytics_overview(db: Session = Depends(get_db), _: User = Depends(require_moderator)) -> Dict[str, int]:
    # Phase 1 metrics
    now = func.now()
    total_users = db.query(func.count(User.id)).scalar() or 0
    new_users_7d = db.query(func.count(User.id)).filter(User.created_at >= func.now() - func.cast("7 days", type_=func.interval())).scalar() if False else None
    # SQLAlchemy interval portable approach (Postgres): use text
    from sqlalchemy import text
    new_users_7d = db.query(func.count(User.id)).filter(User.created_at >= text("now() - interval '7 days'")) .scalar() or 0
    new_users_30d = db.query(func.count(User.id)).filter(User.created_at >= text("now() - interval '30 days'")) .scalar() or 0

    total_photos = db.query(func.count(Photo.id)).scalar() or 0
    new_photos_7d = db.query(func.count(Photo.id)).filter(Photo.created_at >= text("now() - interval '7 days'")) .scalar() or 0
    new_photos_30d = db.query(func.count(Photo.id)).filter(Photo.created_at >= text("now() - interval '30 days'")) .scalar() or 0

    total_votes = db.query(func.count(Vote.id)).scalar() or 0

    users_with_uploads_lifetime = db.query(func.count(func.distinct(Photo.owner_id))).scalar() or 0
    users_with_uploads_30d = db.query(func.count(func.distinct(Photo.owner_id))).filter(Photo.created_at >= text("now() - interval '30 days'")) .scalar() or 0

    rate_limit_hits_7d = 0
    rate_limit_hits_30d = 0

    return {
        "total_users": int(total_users),
        "new_users_7d": int(new_users_7d),
        "new_users_30d": int(new_users_30d),
        "total_photos": int(total_photos),
        "new_photos_7d": int(new_photos_7d),
        "new_photos_30d": int(new_photos_30d),
        "total_votes": int(total_votes),
        "users_with_uploads_lifetime": int(users_with_uploads_lifetime),
        "users_with_uploads_30d": int(users_with_uploads_30d),
        "rate_limit_hits_7d": rate_limit_hits_7d,
        "rate_limit_hits_30d": rate_limit_hits_30d,
    }
