from fastapi import APIRouter, Depends, HTTPException, Request
import hashlib
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session
import httpx
import os

from ..database import get_db
from ..models import User, Photo, Vote
from ..schemas import UserOut, UserCreate
from ..oauth2 import create_access_token, get_current_user

router = APIRouter(prefix="/auth", tags=['Authentication'])

# OAuth configuration
GITHUB_CLIENT_ID = os.getenv("GITHUB_CLIENT_ID", "your_github_client_id")
GITHUB_CLIENT_SECRET = os.getenv("GITHUB_CLIENT_SECRET", "your_github_client_secret")
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "your_google_client_id")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "your_google_client_secret")

from ..config import settings
FRONTEND_URL = os.getenv("FRONTEND_URL", settings.frontend_url)


@router.get("/login/github")
def login_github():
    """Redirect to GitHub OAuth"""
    github_url = (
        f"https://github.com/login/oauth/authorize?"
        f"client_id={GITHUB_CLIENT_ID}&"
        f"scope=user:email&"
        f"redirect_uri={FRONTEND_URL}/auth/callback/github"
    )
    return RedirectResponse(url=github_url)


@router.get("/login/google")
def login_google():
    """Redirect to Google OAuth"""
    google_url = (
        f"https://accounts.google.com/o/oauth2/auth?"
        f"client_id={GOOGLE_CLIENT_ID}&"
        f"redirect_uri={FRONTEND_URL}/auth/callback/google&"
        f"scope=email profile&"
        f"response_type=code"
    )
    return RedirectResponse(url=google_url)


@router.get("/callback/github")
async def github_callback(code: str, db: Session = Depends(get_db)):
    """Handle GitHub OAuth callback"""
    try:
        # Exchange code for access token
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                "https://github.com/login/oauth/access_token",
                data={
                    "client_id": GITHUB_CLIENT_ID,
                    "client_secret": GITHUB_CLIENT_SECRET,
                    "code": code
                },
                headers={"Accept": "application/json"}
            )
            
            token_data = token_response.json()
            access_token = token_data.get("access_token")
            
            if not access_token:
                raise HTTPException(status_code=400, detail="Failed to get access token")
            
            # Get user info
            user_response = await client.get(
                "https://api.github.com/user",
                headers={"Authorization": f"token {access_token}"}
            )
            
            user_data = user_response.json()
            
            # Get email
            email_response = await client.get(
                "https://api.github.com/user/emails",
                headers={"Authorization": f"token {access_token}"}
            )
            
            emails = email_response.json()
            primary_email = next(email["email"] for email in emails if email["primary"])
            
            # Create or get user
            user = db.query(User).filter(
                User.provider == "github",
                User.provider_id == str(user_data["id"])
            ).first()
            
            if not user:
                user = User(
                    email=primary_email,
                    username="anon" + hashlib.sha256(user_data["login"].encode()).hexdigest()[:10],
                    provider="github",
                    provider_id=str(user_data["id"])
                )
                db.add(user)
                db.commit()
                db.refresh(user)
            
            # Create JWT token
            access_token = create_access_token(data={"user_id": user.id})
            
            return RedirectResponse(
                url=f"{FRONTEND_URL}/auth/capture?token={access_token}&next=/categories",
                status_code=302
            )
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/callback/google")
async def google_callback(code: str, db: Session = Depends(get_db)):
    """Handle Google OAuth callback"""
    try:
        # Exchange code for access token
        async with httpx.AsyncClient() as client:
            token_response = await client.post(
                "https://oauth2.googleapis.com/token",
                data={
                    "client_id": GOOGLE_CLIENT_ID,
                    "client_secret": GOOGLE_CLIENT_SECRET,
                    "code": code,
                    "grant_type": "authorization_code",
                    "redirect_uri": f"{FRONTEND_URL}/auth/callback/google"
                }
            )
            
            token_data = token_response.json()
            access_token = token_data.get("access_token")
            
            if not access_token:
                raise HTTPException(status_code=400, detail="Failed to get access token")
            
            # Get user info
            user_response = await client.get(
                "https://www.googleapis.com/oauth2/v2/userinfo",
                headers={"Authorization": f"Bearer {access_token}"}
            )
            
            user_data = user_response.json()
            
            # Create or get user
            user = db.query(User).filter(
                User.provider == "google",
                User.provider_id == user_data["id"]
            ).first()
            
            if not user:
                user = User(
                    email=user_data["email"],
                    username="anon" + hashlib.sha256(user_data["name"].encode()).hexdigest()[:10],
                    provider="google",
                    provider_id=user_data["id"]
                )
                db.add(user)
                db.commit()
                db.refresh(user)
            
            # Create JWT token
            access_token = create_access_token(data={"user_id": user.id})
            
            return RedirectResponse(
                url=f"{FRONTEND_URL}/auth/capture?token={access_token}&next=/categories",
                status_code=302
            )
            
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/me")
def get_current_user_info(current_user: User = Depends(get_current_user)):
    """Get current user info"""
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
        "is_moderator": is_moderator
    }


@router.post("/logout")
def logout():
    """Logout endpoint (client-side token removal)"""
    return {"message": "Logged out successfully"}