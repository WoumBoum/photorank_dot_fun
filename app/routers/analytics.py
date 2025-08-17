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


from fastapi.responses import RedirectResponse
from ..oauth2 import get_current_user


def _is_moderator(user: User) -> bool:
    mod_provider = os.getenv("MODERATOR_PROVIDER")
    mod_id = os.getenv("MODERATOR_PROVIDER_ID")
    return bool(mod_provider and mod_id and user.provider == mod_provider and str(user.provider_id) == str(mod_id))


@router.get("/", response_class=HTMLResponse)
def analytics_page(request: Request, db: Session = Depends(get_db)):
    # Soft guard with redirects for first-load navigations
    # Try to get user via header Bearer from JS fetch-once pattern; otherwise try cookie
    # Reuse get_current_user if Authorization header present; else fall back to cookie manually
    user = None
    # Attempt header-based auth using dependency mimic
    try:
        user = get_current_user.__wrapped__(request=request, db=db)  # type: ignore
    except Exception:
        # Fallback: if not provided or fails, try to read cookie directly
        token = request.cookies.get("access_token")
        if token and token.lower().startswith("bearer "):
            token = token.split(" ", 1)[1]
        if token:
            from ..oauth2 import verify_access_token
            from fastapi import status, HTTPException
            try:
                user_id = verify_access_token(token, HTTPException(status_code=401, detail="Invalid token"))
                user = db.query(User).filter(User.id == user_id).first()
            except Exception:
                user = None

    if not user:
        return RedirectResponse(url="/login", status_code=302)
    if not _is_moderator(user):
        return RedirectResponse(url="/categories", status_code=302)

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
