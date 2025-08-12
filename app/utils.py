from passlib.context import CryptContext
from fastapi import Request
from typing import Optional, Dict, Any

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def hash(password: str):
    return pwd_context.hash(password)


def verify(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)


def get_category_context(request: Request) -> Dict[str, Any]:
    """Get category context from session for templates"""
    return {
        "selected_category_id": request.session.get("selected_category_id"),
        "selected_category_name": request.session.get("selected_category_name")
    }


def require_selected_category(request: Request) -> Optional[int]:
    """Get selected category ID from session, return None if not set"""
    return request.session.get("selected_category_id")
