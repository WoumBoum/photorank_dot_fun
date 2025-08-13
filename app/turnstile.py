from typing import Optional
import httpx
from fastapi import HTTPException, Request
from .config import settings

VERIFY_URL = "https://challenges.cloudflare.com/turnstile/v0/siteverify"

async def verify_turnstile_token(token: Optional[str], ip: Optional[str]) -> bool:
    if not token:
        return False
    data = {
        "secret": settings.cf_turnstile_secret_key,
        "response": token,
    }
    if ip:
        data["remoteip"] = ip
    async with httpx.AsyncClient(timeout=5.0) as client:
        try:
            resp = await client.post(VERIFY_URL, data=data)
            j = resp.json()
            return bool(j.get("success"))
        except Exception:
            return False

async def require_turnstile(request: Request):
    token = None
    # Try header first (AJAX)
    token = request.headers.get("X-Turnstile-Token") or request.headers.get("cf-turnstile-response")
    if token is None:
        # Try form field
        if request.method in {"POST", "PUT", "PATCH"}:
            try:
                form = await request.form()
                token = form.get("cf-turnstile-response")
            except Exception:
                token = None
        # Try JSON
        if token is None:
            try:
                body = await request.json()
                token = body.get("cf_turnstile_response") or body.get("cf-turnstile-response")
            except Exception:
                pass
    ip = request.client.host if request.client else None
    ok = await verify_turnstile_token(token, ip)
    if not ok:
        raise HTTPException(status_code=403, detail="Turnstile verification failed")
