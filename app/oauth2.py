from datetime import datetime, timedelta
from typing import Optional

from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from fastapi import Request, Response
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from fastapi import Depends, HTTPException, status

from . import database, models
from .config import settings

# Define security scheme for token-based authentication
security = HTTPBearer(auto_error=False)

SECRET_KEY = settings.secret_key
ALGORITHM = settings.algorithm
ACCESS_TOKEN_EXPIRE_MINUTES = settings.access_token_expire_minutes


def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)
    return encoded_jwt


def verify_access_token(token: str, credentials_exception):
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("user_id")
        
        if user_id is None:
            raise credentials_exception
            
        return int(user_id)
    except JWTError:
        raise credentials_exception


def _extract_bearer_from_request(request: Optional['Request']) -> Optional[str]:
    try:
        from fastapi import Request as _Req
    except Exception:
        return None
    if request is None:
        return None
    # Header Authorization takes precedence
    auth = request.headers.get("Authorization") if hasattr(request, 'headers') else None
    if auth and auth.lower().startswith("bearer "):
        return auth.split(" ", 1)[1]
    # Cookie fallback: access_token cookie may contain "Bearer <token>" or just token
    if hasattr(request, 'cookies'):
        cookie_val = request.cookies.get("access_token")
        if cookie_val:
            if cookie_val.lower().startswith("bearer "):
                return cookie_val.split(" ", 1)[1]
            return cookie_val
    return None


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(database.get_db)
):
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"}
    )
    
    token = credentials.credentials if credentials and credentials.credentials else None
    # Try extracting from request cookies/headers if missing
    try:
        from fastapi import Request as _Req
    except Exception:
        _Req = None
    request = None
    # FastAPI injects request if we add parameter, but we are avoiding signature change; fallback below won't see it.
    if token is None and 'request' in globals():
        request = globals().get('request')
    token = token or _extract_bearer_from_request(request)
    if token is None:
        raise credentials_exception
    user_id = verify_access_token(token, credentials_exception)
    user = db.query(models.User).filter(models.User.id == user_id).first()
    
    if user is None:
        raise credentials_exception
    
    return user