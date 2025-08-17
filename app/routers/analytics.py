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
def analytics_page(request: Request):
    # Publicly renderable HTML (like other pages). JS will gate via API auth.
    return templates.TemplateResponse("analytics.html", {"request": request})


@router.get("/overview")
def analytics_overview(request: Request, db: Session = Depends(get_db), _: User = Depends(require_moderator)) -> Dict[str, int]:
    # Phase 1 metrics
    now = func.now()
    hide_alts = request.query_params.get('hide_alts', 'true').lower() != 'false'
    alt_ids_env = os.getenv('ALT_USER_IDS', '')
    alt_ids = [int(x) for x in alt_ids_env.split(',') if x.strip().isdigit()]

    user_query = db.query(func.count(User.id))
    if hide_alts and alt_ids:
        user_query = user_query.filter(~User.id.in_(alt_ids))
    total_users = user_query.scalar() or 0
    new_users_7d = db.query(func.count(User.id)).filter(User.created_at >= func.now() - func.cast("7 days", type_=func.interval())).scalar() if False else None
    # SQLAlchemy interval portable approach (Postgres): use text
    from sqlalchemy import text
    new_users_7d_q = db.query(func.count(User.id)).filter(User.created_at >= text("now() - interval '7 days'"))
    new_users_30d_q = db.query(func.count(User.id)).filter(User.created_at >= text("now() - interval '30 days'"))
    if hide_alts and alt_ids:
        new_users_7d_q = new_users_7d_q.filter(~User.id.in_(alt_ids))
        new_users_30d_q = new_users_30d_q.filter(~User.id.in_(alt_ids))
    new_users_7d = new_users_7d_q.scalar() or 0
    new_users_30d = new_users_30d_q.scalar() or 0

    # Photos (filter by owner alts when hiding)
    total_photos_q = db.query(func.count(Photo.id))
    new_photos_7d_q = db.query(func.count(Photo.id)).filter(Photo.created_at >= text("now() - interval '7 days'"))
    new_photos_30d_q = db.query(func.count(Photo.id)).filter(Photo.created_at >= text("now() - interval '30 days'"))
    if hide_alts and alt_ids:
        total_photos_q = total_photos_q.filter(~Photo.owner_id.in_(alt_ids))
        new_photos_7d_q = new_photos_7d_q.filter(~Photo.owner_id.in_(alt_ids))
        new_photos_30d_q = new_photos_30d_q.filter(~Photo.owner_id.in_(alt_ids))
    total_photos = total_photos_q.scalar() or 0
    new_photos_7d = new_photos_7d_q.scalar() or 0
    new_photos_30d = new_photos_30d_q.scalar() or 0

    # Total votes (filter by voter alts when hiding)
    total_votes_q = db.query(func.count(Vote.id))
    if hide_alts and alt_ids:
        total_votes_q = total_votes_q.filter(~Vote.user_id.in_(alt_ids))
    total_votes = total_votes_q.scalar() or 0

    u_life_q = db.query(func.count(func.distinct(Photo.owner_id)))
    u_30_q = db.query(func.count(func.distinct(Photo.owner_id))).filter(Photo.created_at >= text("now() - interval '30 days'"))
    if hide_alts and alt_ids:
        u_life_q = u_life_q.filter(~Photo.owner_id.in_(alt_ids))
        u_30_q = u_30_q.filter(~Photo.owner_id.in_(alt_ids))
    users_with_uploads_lifetime = u_life_q.scalar() or 0
    users_with_uploads_30d = u_30_q.scalar() or 0

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


@router.get("/time-series")
def analytics_time_series(request: Request, db: Session = Depends(get_db), _: User = Depends(require_moderator)):
    """Return time-series for:
    - votes/day
    - unique voters/day
    - cumulative users/day
    - DAU/WAU/MAU (activity from votes or uploads)
    Dates are YYYY-MM-DD (UTC), contiguous from first data date to today.
    """
    # Find min created_at across users, photos, votes
    min_user = db.query(func.min(User.created_at)).scalar()
    min_photo = db.query(func.min(Photo.created_at)).scalar()
    min_vote = db.query(func.min(Vote.created_at)).scalar()

    min_date = min([d for d in [min_user, min_photo, min_vote] if d is not None], default=None)
    if min_date is None:
        # No data yet; return empty series for today
        today = datetime.utcnow().date()
        date_str = today.strftime("%Y-%m-%d")
        empty = [{"date": date_str, "count": 0}]
        return {
            "votes_per_day": empty,
            "unique_voters_per_day": empty,
            "users_cumulative_per_day": empty,
            "dau_per_day": empty,
            "wau_per_day": empty,
            "mau_per_day": empty,
        }

    start_date = min_date.date()
    today = datetime.utcnow().date()

    # Helper: generate date range
    days = (today - start_date).days
    full_dates = [start_date + timedelta(days=i) for i in range(days + 1)]

    hide_alts = request.query_params.get('hide_alts', 'true').lower() != 'false'
    alt_ids_env = os.getenv('ALT_USER_IDS', '')
    alt_ids = [int(x) for x in alt_ids_env.split(',') if x.strip().isdigit()]

    # votes per day
    vote_q = db.query(func.date_trunc('day', Vote.created_at).label('day'), func.count(Vote.id))
    if hide_alts and alt_ids:
        vote_q = vote_q.filter(~Vote.user_id.in_(alt_ids))
    votes_rows = (
        vote_q
        .group_by('day')
        .order_by('day')
        .all()
    )
    votes_map = {r[0].date(): int(r[1]) for r in votes_rows}

    # unique voters per day
    unique_q = db.query(func.date_trunc('day', Vote.created_at).label('day'), func.count(func.distinct(Vote.user_id)))
    if hide_alts and alt_ids:
        unique_q = unique_q.filter(~Vote.user_id.in_(alt_ids))
    unique_rows = (
        unique_q
        .group_by('day')
        .order_by('day')
        .all()
    )
    unique_map = {r[0].date(): int(r[1]) for r in unique_rows}

    # users cumulative per day: first get new users per day (respect hide_alts)
    new_user_q = db.query(func.date_trunc('day', User.created_at).label('day'), func.count(User.id))
    if hide_alts and alt_ids:
        new_user_q = new_user_q.filter(~User.id.in_(alt_ids))
    new_user_rows = (
        new_user_q
        .group_by('day')
        .order_by('day')
        .all()
    )
    new_user_map = {r[0].date(): int(r[1]) for r in new_user_rows}

    users_cum = []
    running = 0
    for d in full_dates:
        running += new_user_map.get(d, 0)
        users_cum.append({"date": d.strftime("%Y-%m-%d"), "count": running})

    votes_series = [{"date": d.strftime("%Y-%m-%d"), "count": votes_map.get(d, 0)} for d in full_dates]
    unique_series = [{"date": d.strftime("%Y-%m-%d"), "count": unique_map.get(d, 0)} for d in full_dates]

    # Activity sets per day: users who voted or uploaded
    vote_user_q = db.query(func.date_trunc('day', Vote.created_at).label('day'), Vote.user_id)
    if hide_alts and alt_ids:
        vote_user_q = vote_user_q.filter(~Vote.user_id.in_(alt_ids))
    vote_user_rows = (
        vote_user_q
        .all()
    )
    upload_user_q = db.query(func.date_trunc('day', Photo.created_at).label('day'), Photo.owner_id)
    if hide_alts and alt_ids:
        upload_user_q = upload_user_q.filter(~Photo.owner_id.in_(alt_ids))
    upload_user_rows = (
        upload_user_q
        .all()
    )
    # Build per-day sets
    per_day_users = {d: set() for d in full_dates}
    for day_dt, uid in vote_user_rows:
        if day_dt is None or uid is None:
            continue
        day = day_dt.date()
        if day in per_day_users:
            per_day_users[day].add(uid)
    for day_dt, uid in upload_user_rows:
        if day_dt is None or uid is None:
            continue
        day = day_dt.date()
        if day in per_day_users:
            per_day_users[day].add(uid)

    # DAU
    dau_series = [{"date": d.strftime("%Y-%m-%d"), "count": len(per_day_users.get(d, set()))} for d in full_dates]

    # WAU: rolling 7-day inclusive window [d-6, d]
    from collections import deque
    window = deque()
    window_sets = deque()
    wau_series = []
    active_union = set()
    for d in full_dates:
        # add current day
        window.append(d)
        todays = per_day_users.get(d, set())
        window_sets.append(todays)
        active_union |= todays
        # drop days older than 6 days before d
        while (d - window[0]).days > 6:
            old_day = window.popleft()
            old_set = window_sets.popleft()
            # remove old_set from union by recomputing (safe and simple)
            active_union = set().union(*window_sets) if window_sets else set()
        wau_series.append({"date": d.strftime("%Y-%m-%d"), "count": len(active_union)})

    # MAU: rolling 30-day inclusive window [d-29, d]
    window = deque()
    window_sets = deque()
    mau_series = []
    active_union = set()
    for d in full_dates:
        window.append(d)
        todays = per_day_users.get(d, set())
        window_sets.append(todays)
        active_union |= todays
        while (d - window[0]).days > 29:
            old_day = window.popleft()
            old_set = window_sets.popleft()
            active_union = set().union(*window_sets) if window_sets else set()
        mau_series.append({"date": d.strftime("%Y-%m-%d"), "count": len(active_union)})

    return {
        "votes_per_day": votes_series,
        "unique_voters_per_day": unique_series,
        "users_cumulative_per_day": users_cum,
        "dau_per_day": dau_series,
        "wau_per_day": wau_series,
        "mau_per_day": mau_series,
    }
