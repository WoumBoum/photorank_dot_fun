import hashlib
import uuid
from datetime import datetime, timedelta
from typing import Optional

from fastapi import Request, HTTPException
from sqlalchemy.orm import Session

from .models import GuestVote, GuestVoteLimit

# Guest voting configuration
GUEST_VOTE_LIMIT = 10  # Votes per session
GUEST_SESSION_DURATION = timedelta(hours=24)  # Session expiration


def generate_session_id() -> str:
    """Generate a unique session ID for guest users"""
    return str(uuid.uuid4())


def get_guest_session_id(request: Request) -> str:
    """Get or create guest session ID from cookie"""
    session_id = request.cookies.get("guest_session")
    
    if not session_id or not is_valid_session_id(session_id):
        session_id = generate_session_id()
    
    return session_id


def is_valid_session_id(session_id: str) -> bool:
    """Validate session ID format"""
    try:
        uuid.UUID(session_id)
        return True
    except ValueError:
        return False


def hash_ip_address(ip: str) -> str:
    """Hash IP address for privacy"""
    if not ip:
        return ""
    salt = "photorank_guest_salt"  # Should be from environment in production
    return hashlib.sha256(f"{ip}{salt}".encode()).hexdigest()


def hash_user_agent(user_agent: str) -> str:
    """Hash user agent for privacy"""
    if not user_agent:
        return ""
    salt = "photorank_guest_ua_salt"  # Should be from environment in production
    return hashlib.sha256(f"{user_agent}{salt}".encode()).hexdigest()


def get_client_info(request: Request) -> tuple[str, str]:
    """Get hashed client information for rate limiting"""
    ip = request.client.host if request.client else ""
    user_agent = request.headers.get("user-agent", "")
    
    return hash_ip_address(ip), hash_user_agent(user_agent)


def can_guest_vote(session_id: str, db: Session) -> bool:
    """Check if guest can vote based on rate limits"""
    vote_limit = db.query(GuestVoteLimit).filter(
        GuestVoteLimit.session_id == session_id
    ).first()
    
    if not vote_limit:
        return True  # New session, can vote
    
    # Check if session is expired (24 hours)
    session_age = datetime.utcnow() - vote_limit.created_at
    if session_age > GUEST_SESSION_DURATION:
        # Reset expired session - just return True, let caller handle cleanup
        return True
    
    # Check vote count
    return vote_limit.vote_count < GUEST_VOTE_LIMIT


def record_guest_vote(session_id: str, winner_id: int, loser_id: int, 
                     ip_hash: str, user_agent_hash: str, db: Session) -> None:
    """Record a guest vote and update rate limits - caller must commit"""
    # Create guest vote record
    guest_vote = GuestVote(
        session_id=session_id,
        winner_id=winner_id,
        loser_id=loser_id,
        ip_hash=ip_hash,
        user_agent_hash=user_agent_hash
    )
    db.add(guest_vote)
    
    # Update vote count
    vote_limit = db.query(GuestVoteLimit).filter(
        GuestVoteLimit.session_id == session_id
    ).first()
    
    if vote_limit:
        vote_limit.vote_count += 1
        vote_limit.last_vote_date = datetime.utcnow()
    else:
        vote_limit = GuestVoteLimit(
            session_id=session_id,
            vote_count=1
        )
        db.add(vote_limit)


def get_remaining_guest_votes(session_id: str, db: Session) -> int:
    """Get remaining votes for guest session"""
    vote_limit = db.query(GuestVoteLimit).filter(
        GuestVoteLimit.session_id == session_id
    ).first()
    
    if not vote_limit:
        return GUEST_VOTE_LIMIT
    
    # Check if session expired
    session_age = datetime.utcnow() - vote_limit.created_at
    if session_age > GUEST_SESSION_DURATION:
        # Session expired - just return full limit, let caller handle cleanup
        return GUEST_VOTE_LIMIT
    
    return max(0, GUEST_VOTE_LIMIT - vote_limit.vote_count)


def migrate_guest_votes_to_user(session_id: str, user_id: int, db: Session) -> int:
    """Migrate guest votes to a user account and return count migrated"""
    from .models import Vote
    
    guest_votes = db.query(GuestVote).filter(
        GuestVote.session_id == session_id
    ).all()
    
    migrated_count = 0
    
    for guest_vote in guest_votes:
        # Check if user already voted on this pair
        existing_vote = db.query(Vote).filter(
            Vote.user_id == user_id,
            ((Vote.winner_id == guest_vote.winner_id) & (Vote.loser_id == guest_vote.loser_id)) |
            ((Vote.winner_id == guest_vote.loser_id) & (Vote.loser_id == guest_vote.winner_id))
        ).first()
        
        if not existing_vote:
            # Create user vote
            user_vote = Vote(
                user_id=user_id,
                winner_id=guest_vote.winner_id,
                loser_id=guest_vote.loser_id
            )
            db.add(user_vote)
            migrated_count += 1
    
    # Clean up guest votes and limits
    db.query(GuestVote).filter(GuestVote.session_id == session_id).delete()
    db.query(GuestVoteLimit).filter(GuestVoteLimit.session_id == session_id).delete()
    
    db.commit()
    return migrated_count