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
    try:
        # Check if photos exist
        winner = db.query(Photo).filter(Photo.id == vote.winner_id).first()
        loser = db.query(Photo).filter(Photo.id == vote.loser_id).first()
        
        if not winner or not loser:
            raise HTTPException(status_code=404, detail="Photo not found")
        
        if winner.id == loser.id:
            raise HTTPException(status_code=400, detail="Cannot vote for same photo")
        
        # Get guest session and check rate limits
        original_cookie = request.cookies.get("guest_session")
        session_id = get_guest_session_id(request)
        ip_hash, user_agent_hash = get_client_info(request)
        
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
                raise HTTPException(
                    status_code=429, 
                    detail="Guest vote limit reached. Please sign up to continue voting."
                )
        except Exception as e:
            # If guest voting tables don't exist, fall back to allowing votes
            # This prevents 500 errors when tables are missing
            print(f"Guest voting tables may not exist: {e}")
            # Continue with the vote - this allows the system to work even if guest tables are missing
        
        # Calculate ELO changes (same logic as authenticated votes)
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
        
        # Record guest vote if tables exist
        try:
            record_guest_vote(session_id, vote.winner_id, vote.loser_id, 
                            ip_hash, user_agent_hash, db)
        except Exception as e:
            print(f"Failed to record guest vote (tables may not exist): {e}")
            # Continue even if guest vote recording fails
        
        # Commit all changes
        db.commit()
        
        # Create response payload (without user_id since it's a guest vote)
        payload = VoteOut(
            id=0,
            user_id=None,
            winner_id=vote.winner_id,
            loser_id=vote.loser_id,
            created_at=datetime.utcnow()
        )
        
        # Build JSONResponse and set cookie if newly created
        resp = JSONResponse(content=payload.dict())
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
        raise
    except Exception as e:
        # Log unexpected errors but return a proper response
        print(f"Unexpected error in guest vote: {e}")
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
    try:
        original_cookie = request.cookies.get("guest_session")
        session_id = get_guest_session_id(request)
        
        # Get remaining votes with error handling
        try:
            remaining_votes = get_remaining_guest_votes(session_id, db)
        except Exception as e:
            # If guest voting tables don't exist, return full limit
            print(f"Guest voting tables may not exist: {e}")
            remaining_votes = 10  # Default limit
    
        payload = {
            "remaining_votes": remaining_votes,
            "total_limit": 10,
            "session_id": session_id
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
        
        return resp
    
    except Exception as e:
        # Log unexpected errors but return a proper response
        print(f"Unexpected error in guest stats: {e}")
        return JSONResponse(content={
            "remaining_votes": 10,
            "total_limit": 10,
            "session_id": "error"
        })