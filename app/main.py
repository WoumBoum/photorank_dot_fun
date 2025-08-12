from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from fastapi import FastAPI, Request
from starlette.middleware.sessions import SessionMiddleware

from .config import description, title
from .routers import auth, photos, votes, websocket, users, categories
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
# WebSocket endpoint (mounted directly)
from .routers.websocket import websocket_endpoint
app.add_api_websocket_route("/ws", websocket_endpoint)

# Frontend routes
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from fastapi import Request

templates = Jinja2Templates(directory="app/templates")

@app.get("/", response_class=HTMLResponse)
def index(request: Request):
    context = {"request": request}
    context.update(get_category_context(request))
    return templates.TemplateResponse("index.html", context)

@app.get("/leaderboard", response_class=HTMLResponse)
def leaderboard(request: Request):
    context = {"request": request}
    context.update(get_category_context(request))
    return templates.TemplateResponse("leaderboard.html", context)

@app.get("/upload", response_class=HTMLResponse)
def upload(request: Request):
    context = {"request": request}
    context.update(get_category_context(request))
    return templates.TemplateResponse("upload.html", context)

@app.get("/stats", response_class=HTMLResponse)
def stats(request: Request):
    context = {"request": request}
    context.update(get_category_context(request))
    return templates.TemplateResponse("stats.html", context)

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