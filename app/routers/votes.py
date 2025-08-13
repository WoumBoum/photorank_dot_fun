from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from ..database import get_db
from ..models import Vote, Photo, User
from ..schemas import VoteCreate, VoteOut
from ..oauth2 import get_current_user
from ..turnstile import require_turnstile

router = APIRouter(prefix="/votes", tags=['Votes'])

K_FACTOR = 32


def calculate_elo_change(winner_rating: float, loser_rating: float) -> tuple[float, float]:
    """Calculate ELO rating changes"""
    expected_winner = 1 / (1 + 10 ** ((loser_rating - winner_rating) / 400))
    expected_loser = 1 - expected_winner
    
    winner_change = K_FACTOR * (1 - expected_winner)
    loser_change = K_FACTOR * (0 - expected_loser)
    
    return winner_change, loser_change


@router.post("/", response_model=VoteOut, dependencies=[Depends(__import__('app.turnstile', fromlist=['require_turnstile']).require_turnstile)])
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