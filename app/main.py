from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, Request
from starlette.middleware.sessions import SessionMiddleware
from starlette.middleware.trustedhost import TrustedHostMiddleware

from .config import description, title
from .routers import auth, photos, votes, websocket, users, categories, analytics
from .utils import get_category_context

app = FastAPI(
    title=title,
    description=description,
    version="1.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# Session middleware
app.add_middleware(SessionMiddleware, secret_key="your-secret-key-change-in-production")

# Restrict hosts; proxy headers handled by Uvicorn
app.add_middleware(TrustedHostMiddleware, allowed_hosts=["photorank.fun", "www.photorank.fun", "photorank-00e51b.onrender.com", "localhost", "127.0.0.1"]) 

# CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# API routes
app.include_router(auth.router)
app.include_router(photos.router, prefix="/api")
app.include_router(votes.router, prefix="/api")
app.include_router(users.router, prefix="/api")
app.include_router(categories.router, prefix="/api")
# Analytics (moderator-only)
from .routers import analytics as analytics_router
app.include_router(analytics_router.router)
# WebSocket endpoint (mounted directly)
from .routers.websocket import websocket_endpoint
app.add_api_websocket_route("/ws", websocket_endpoint)

# Frontend routes
from fastapi.responses import HTMLResponse, RedirectResponse, PlainTextResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request

templates = Jinja2Templates(directory="app/templates")

@app.get("/")
def index_redirect():
    return RedirectResponse(url="/categories", status_code=307)

@app.get("/leaderboard")
def leaderboard_redirect():
    return RedirectResponse(url="/categories", status_code=307)

@app.get("/{category_name}/leaderboard", response_class=HTMLResponse)
def leaderboard_by_category(category_name: str, request: Request):
    context = {"request": request, "category_name": category_name}
    context.update(get_category_context(request))
    return templates.TemplateResponse("leaderboard.html", context)

@app.get("/upload")
def upload_redirect():
    return RedirectResponse(url="/categories", status_code=307)

@app.get("/{category_name}/upload", response_class=HTMLResponse)
def upload_by_category(category_name: str, request: Request):
    from .database import get_db
    from .routers.photos import is_admin_user
    from .models import User
    from .config import settings
    from jose import JWTError, jwt
    import os

    context = {"request": request, "category_name": category_name}
    context.update(get_category_context(request))

    # Check if user is admin
    is_admin = False
    try:
        # Get token from localStorage (frontend) or Authorization header
        token = None
        if "authorization" in request.headers:
            auth_header = request.headers["authorization"]
            if auth_header.startswith("Bearer "):
                token = auth_header[7:]  # Remove "Bearer " prefix
                print(f"DEBUG: Found token in Authorization header")

        if token:
            payload = jwt.decode(token, settings.secret_key, algorithms=[settings.algorithm])
            user_id = payload.get("user_id")
            print(f"DEBUG: Decoded user_id: {user_id}")
            if user_id:
                db = next(get_db())
                current_user = db.query(User).filter(User.id == user_id).first()
                print(f"DEBUG: Found user: {current_user.username if current_user else 'None'}")
                if current_user:
                    is_admin = is_admin_user(current_user)
                    print(f"DEBUG: is_admin result: {is_admin}")
    except (JWTError, Exception) as e:
        # If token is invalid or any error occurs, user is not admin
        print(f"DEBUG: Error in admin check: {e}")
        is_admin = False

    print(f"DEBUG: Final is_admin value: {is_admin}")
    print(f"DEBUG: MODERATOR_PROVIDER env: {os.getenv('MODERATOR_PROVIDER')}")
    print(f"DEBUG: MODERATOR_PROVIDER_ID env: {os.getenv('MODERATOR_PROVIDER_ID')}")
    context["is_admin"] = is_admin

    return templates.TemplateResponse("upload.html", context)

@app.get("/stats", response_class=HTMLResponse)
def stats(request: Request):
    context = {"request": request}
    context.update(get_category_context(request))
    return templates.TemplateResponse("stats.html", context)

@app.get("/{category_name}/vote", response_class=HTMLResponse)
def vote_by_category(category_name: str, request: Request):
    context = {"request": request, "category_name": category_name}
    context.update(get_category_context(request))
    return templates.TemplateResponse("index.html", context)

@app.get("/login", response_class=HTMLResponse)
def login(request: Request):
    context = {"request": request}
    context.update(get_category_context(request))
    return templates.TemplateResponse("login.html", context)

@app.get("/categories", response_class=HTMLResponse)
def categories_page(request: Request):
    context = {"request": request}
    context.update(get_category_context(request))
    return templates.TemplateResponse("categories.html", context)

@app.get("/categories/new", response_class=HTMLResponse)
def categories_new_page(request: Request):
    context = {"request": request}
    context.update(get_category_context(request))
    return templates.TemplateResponse("category_new.html", context)

@app.get("/auth/capture", response_class=HTMLResponse)
def auth_capture(request: Request):
    # Minimal page: store token to localStorage, then redirect client-side
    return HTMLResponse("""
<!doctype html><html><head><meta charset=\"utf-8\"><title>Auth</title></head>
<body>
<script>
(function(){
  var params=new URLSearchParams(window.location.search);
  var token=params.get('token');
  var dest=params.get('next')||'/categories';
  if(token){try{localStorage.setItem('token',token);}catch(e){}}
  window.location.replace(dest);
})();
</script>
</body></html>
""")
