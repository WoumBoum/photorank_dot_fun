# PhotoRank Project Structure

## Overview
Ultra-minimalist photo ranking app using ELO system with brutalist design.

## Directory Structure
```
fastapi-social-media-app/
├── app/                          # Main application
│   ├── routers/                  # API endpoints
│   │   ├── auth.py              # OAuth + JWT
│   │   ├── photos.py            # Upload/delete photos
│   │   ├── votes.py             # ELO voting
│   │   ├── users.py             # User stats
│   │   └── websocket.py         # Real-time updates
│   ├── templates/               # Jinja2 HTML
│   ├── static/                  # CSS, JS, uploads
│   ├── models.py                # Database models
│   ├── schemas.py               # Pydantic schemas
│   └── main.py                  # FastAPI app
├── tests/                       # Test suite
├── alembic/                     # Database migrations
├── docker-compose-dev.yml       # Development setup
├── docker-compose-prod.yml      # Production setup
└── requirements.txt             # Dependencies
```

## Key Files
- **app/main.py:19** - FastAPI application setup
- **app/models.py:15** - Database models (User, Photo, Vote)
- **app/routers/photos.py:91** - Upload limit (5/day)
- **app/routers/votes.py:45** - ELO calculation (K=32)
- **app/static/css/style.css:84** - Brutalist design

## Quick Commands
```bash
# Start development
docker compose -f docker-compose-dev.yml up -d

# Run tests
python run_tests.py

# Database migration
alembic revision --autogenerate -m "description"
```

## URLs
- **App**: http://localhost:9001
- **Login**: http://localhost:9001/login
- **Upload**: http://localhost:9001/upload
- **Leaderboard**: http://localhost:9001/leaderboard
- **Stats**: http://localhost:9001/stats