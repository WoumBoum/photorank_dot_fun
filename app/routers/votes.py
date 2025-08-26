from fastapi import APIRouter, Depends, HTTPException, Request
from starlette.responses import Response, JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import Tuple
from datetime import datetime, timedelta

from ..database import get_db
from ..models import Vote, Photo, User, GuestVote, GuestVoteLimit
from ..schemas import VoteCreate, VoteOut
from ..oauth2 import get_current_user
from ..guest_utils import get_guest_session_id, get_client_info, can_guest_vote, record_guest_vote, get_remaining_guest_votes

router = APIRouter(prefix="/votes", tags=['Votes'])

K_FACTOR = 32


def calculate_elo_change(winner_rating: float, loser_rating: float) -> Tuple[float, float]:
    """Calculate ELO rating changes"""
    expected_winner = 1 / (1 + 10 ** ((loser_rating - winner_rating) / 400))
    expected_loser = 1 - expected_winner
    
    winner_change = K_FACTOR * (1 - expected_winner)
    loser_change = K_FACTOR * (0 - expected_loser)
    
    return winner_change, loser_change


@router.post("/", response_model=VoteOut)
def create_vote(
    vote: VoteCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Submit a vote and update ELO ratings"""
    # Check if photos exist
    winner = db.query(Photo).filter(Photo.id == vote.winner_id).first()
    loser = db.query(Photo).filter(Photo.id == vote.loser_id).first()
    
    if not winner or not loser:
        raise HTTPException(status_code=404, detail="Photo not found")
    
    if winner.id == loser.id:
        raise HTTPException(status_code=400, detail="Cannot vote for same photo")
    
    # Check if user already voted on this pair
    existing_vote = db.query(Vote).filter(
        Vote.user_id == current_user.id,
        ((Vote.winner_id == vote.winner_id) & (Vote.loser_id == vote.loser_id)) |
        ((Vote.winner_id == vote.loser_id) & (Vote.loser_id == vote.winner_id))
    ).first()
    
    if existing_vote:
        raise HTTPException(status_code=400, detail="Already voted on this pair")
    
    # Calculate ELO changes
    winner_change, loser_change = calculate_elo_change(
        winner.elo_rating, 
        loser.elo_rating
    )
    
    # Update ratings
    winner.elo_rating += winner_change
    loser.elo_rating += loser_change
    
    # Update duel counts
    winner.total_duels += 1
    loser.total_duels += 1
    winner.wins += 1
    
    # Update user's total votes count
    try:
        current_user.total_votes = (current_user.total_votes or 0) + 1
        db.add(current_user)
    except Exception:
        # Be resilient: do not block vote creation if counter update fails
        pass
    
    # Create vote record
    new_vote = Vote(
        user_id=current_user.id,
        winner_id=vote.winner_id,
        loser_id=vote.loser_id
    )
    
    db.add(new_vote)
    db.commit()
    db.refresh(new_vote)
    
    return VoteOut(
        id=new_vote.id,
        user_id=new_vote.user_id,
        winner_id=new_vote.winner_id,
        loser_id=new_vote.loser_id,
        created_at=new_vote.created_at
    )


@router.get("/stats")
def get_vote_stats(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get voting statistics for current user"""
    total_votes = db.query(Vote).filter(Vote.user_id == current_user.id).count()
    
    return {
        "total_votes": total_votes
    }


@router.post("/guest", response_model=VoteOut)
def create_guest_vote(
    vote: VoteCreate,
    request: Request,
    db: Session = Depends(get_db)
):
    """Submit a vote as a guest user"""
    print(f"[GUEST_VOTE] Starting guest vote: winner_id={vote.winner_id}, loser_id={vote.loser_id}")
    try:
        # Check if photos exist
        print(f"[GUEST_VOTE] Checking if photos exist...")
        winner = db.query(Photo).filter(Photo.id == vote.winner_id).first()
        loser = db.query(Photo).filter(Photo.id == vote.loser_id).first()

        if not winner or not loser:
            print(f"[GUEST_VOTE] Photo not found: winner={winner}, loser={loser}")
            raise HTTPException(status_code=404, detail="Photo not found")

        if winner.id == loser.id:
            print(f"[GUEST_VOTE] Same photo error")
            raise HTTPException(status_code=400, detail="Cannot vote for same photo")

        # Get guest session and check rate limits
        original_cookie = request.cookies.get("guest_session")
        session_id = get_guest_session_id(request)
        ip_hash, user_agent_hash = get_client_info(request)
        print(f"[GUEST_VOTE] Session: {session_id}, cookie_present={original_cookie is not None}")
        
        # Check if guest can vote using the can_guest_vote function
        if not can_guest_vote(session_id, db):
            raise HTTPException(
                status_code=429, 
                detail="Guest vote limit reached. Please sign up to continue voting."
            )
        
        # Check for expired session and cleanup if needed
        try:
            vote_limit = db.query(GuestVoteLimit).filter(
                GuestVoteLimit.session_id == session_id
            ).first()
            
            if vote_limit:
                session_age = datetime.utcnow() - vote_limit.created_at
                if session_age > timedelta(hours=24):
                    # Clean up expired session
                    db.query(GuestVote).filter(GuestVote.session_id == session_id).delete()
                    db.query(GuestVoteLimit).filter(GuestVoteLimit.session_id == session_id).delete()
                    vote_limit = None
            
            if vote_limit and vote_limit.vote_count >= 10:
                print(f"[GUEST_VOTE][LIMIT] session_id={session_id} vote_count={vote_limit.vote_count}/10")
                raise HTTPException(
                    status_code=429, 
                    detail={
                        "message": "Guest vote limit reached. Please sign up to continue voting.",
                        "reason": "limit_exhausted",
                        "session_id": session_id,
                        "vote_count": vote_limit.vote_count,
                        "limit": 10
                    }
                )
        except Exception as e:
            # Distinguish between rate-limit exhaustion and backend issues
            print(f"[GUEST_VOTE][ERROR] Guest voting backend unavailable: {type(e).__name__}: {e}")
            raise HTTPException(
                status_code=500,
                detail="Guest voting system not available. Please try again later or sign up."
            )
        
        # Calculate ELO changes (same logic as authenticated votes)
        print(f"[GUEST_VOTE] Calculating ELO: winner_rating={winner.elo_rating}, loser_rating={loser.elo_rating}")
        winner_change, loser_change = calculate_elo_change(
            winner.elo_rating,
            loser.elo_rating
        )
        print(f"[GUEST_VOTE] ELO changes: winner_change={winner_change}, loser_change={loser_change}")

        # Update ratings
        print(f"[GUEST_VOTE] Updating ratings...")
        winner.elo_rating += winner_change
        loser.elo_rating += loser_change

        # Update duel counts
        winner.total_duels += 1
        loser.total_duels += 1
        winner.wins += 1
        print(f"[GUEST_VOTE] Updated duel counts")
        
        # Record guest vote if tables exist
        try:
            record_guest_vote(session_id, vote.winner_id, vote.loser_id, 
                            ip_hash, user_agent_hash, db)
        except Exception as e:
            print(f"Failed to record guest vote (tables may not exist): {e}")
            # Continue even if guest vote recording fails
        
        # Commit all changes
        try:
            # Diagnostic: show current vote_count before commit
            try:
                _vl = db.query(GuestVoteLimit).filter(GuestVoteLimit.session_id == session_id).first()
                print(f"[GUEST_VOTE][COUNTER] session_id={session_id} new_vote_count={_vl.vote_count if _vl else 'None'}")
            except Exception:
                pass
            db.commit()
        except Exception as e:
            print(f"Failed to commit guest vote changes: {e}")
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail="Database error. Please try again."
            )

        # Create response payload (without user_id since it's a guest vote)
        payload = VoteOut(
            id=0,
            user_id=None,
            winner_id=vote.winner_id,
            loser_id=vote.loser_id,
            created_at=datetime.utcnow()
        )

        # Convert to dict and handle datetime serialization
        payload_dict = payload.dict()
        payload_dict['created_at'] = payload_dict['created_at'].isoformat()

        # Build JSONResponse and set cookie if newly created
        resp = JSONResponse(content=payload_dict)
        if not original_cookie or original_cookie != session_id:
            # 24h, Lax to allow same-site nav, secure recommended in prod
            resp.set_cookie(
                key="guest_session",
                value=session_id,
                max_age=24*60*60,
                httponly=False,
                samesite="Lax"
            )

        return resp
    
    except HTTPException:
        # Re-raise HTTP exceptions
        print(f"[GUEST_VOTE] HTTPException raised, re-raising")
        raise
    except Exception as e:
        # Log unexpected errors but return a proper response
        print(f"[GUEST_VOTE] Unexpected error: {type(e).__name__}: {e}")
        import traceback
        print(f"[GUEST_VOTE] Traceback: {traceback.format_exc()}")
        raise HTTPException(
            status_code=500,
            detail="Internal server error. Please try again."
        )


@router.get("/guest/stats")
def get_guest_vote_stats(
    request: Request,
    db: Session = Depends(get_db)
):
    """Get guest voting statistics"""
    print(f"[GUEST_STATS] Starting guest stats request")
    try:
        original_cookie = request.cookies.get("guest_session")
        session_id = get_guest_session_id(request)
        print(f"[GUEST_STATS] Session: {session_id}, cookie_present={original_cookie is not None}")

        # Get remaining votes with error handling
        try:
            print(f"[GUEST_STATS] Getting remaining votes...")
            # Raw debug
            try:
                raw = db.query(GuestVoteLimit).filter(GuestVoteLimit.session_id == session_id).first()
                raw_count = raw.vote_count if raw else None
                print(f"[GUEST_STATS][RAW] session_id={session_id} vote_count={raw_count}")
            except Exception as raw_e:
                print(f"[GUEST_STATS][RAW][ERROR] {type(raw_e).__name__}: {raw_e}")
                raw_count = None
            remaining_votes = get_remaining_guest_votes(session_id, db)
            print(f"[GUEST_STATS] Remaining votes: {remaining_votes}")
        except Exception as e:
            # Backend issue fetching remaining votes
            print(f"[GUEST_STATS][FALLBACK] Backend unavailable while fetching remaining votes: {type(e).__name__}: {e}")
            remaining_votes = 0  # No votes available if backend is unavailable

        # Attach reason for observability based on raw_count if available
        try:
            raw = db.query(GuestVoteLimit).filter(GuestVoteLimit.session_id == session_id).first()
            raw_count = raw.vote_count if raw else None
        except Exception:
            raw_count = None
        if raw_count is None:
            reason = "no_session"
        elif raw_count >= 10:
            reason = "limit_exhausted"
        else:
            reason = "ok"
        payload = {
            "remaining_votes": remaining_votes,
            "total_limit": 10,
            "session_id": session_id,
            "reason": reason
        }
        resp = JSONResponse(content=payload)
        if not original_cookie or original_cookie != session_id:
            resp.set_cookie(
                key="guest_session",
                value=session_id,
                max_age=24*60*60,
                httponly=False,
                samesite="Lax"
            )

        print(f"[GUEST_STATS] Returning stats: {payload}")
        return resp

    except Exception as e:
        # Log unexpected errors but return a proper response
        print(f"[GUEST_STATS] Unexpected error: {type(e).__name__}: {e}")
        import traceback
        print(f"[GUEST_STATS] Traceback: {traceback.format_exc()}")
        return JSONResponse(content={
            "remaining_votes": 10,
            "total_limit": 10,
            "session_id": "error"
        })