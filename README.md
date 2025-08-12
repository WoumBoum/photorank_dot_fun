# PhotoRank - Brutalist Photo Ranking App

An ultra-minimalist photo ranking application that uses the ELO rating system to rank photos through direct comparison voting. Built with FastAPI, PostgreSQL, and brutalist design principles.

## Features

- **ELO Ranking System**: Photos ranked using proven ELO algorithm (K=32)
- **Direct Comparison Voting**: Users vote between two photos at a time
- **Rate Limiting**: 5 uploads per user per 24 hours
- **Photo Management**: Upload, view, and delete your own photos
- **Leaderboard**: Top 100 photos with crown icons for top 3 (≥50 duels required)
- **User Stats**: View your photo rankings and performance metrics
- **Brutalist Design**: Clean, minimalist aesthetic with monospace typography
- **OAuth Authentication**: GitHub and Google login support
- **Real-time Updates**: WebSocket for live leaderboard updates

## Tech Stack

- **Backend**: FastAPI with Python 3.9+
- **Frontend**: Jinja2 Templates with brutalist CSS
- **Database**: PostgreSQL with SQLAlchemy ORM
- **Authentication**: OAuth2 (GitHub/Google) with JWT tokens
- **Containerization**: Docker & Docker Compose
- **Testing**: pytest with comprehensive test coverage

## Quick Start

### Docker (Recommended)
```bash
git clone https://github.com/mvarrone/fastapi-social-media-app.git
cd fastapi-social-media-app
docker compose -f docker-compose-dev.yml up -d
```

Visit: http://localhost:9001

### Manual Setup
```bash
# Create virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: .\venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Run development server
uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
```

## API Documentation
- **Swagger UI**: http://localhost:9001/api/docs
- **ReDoc**: http://localhost:9001/api/redoc

## Development

### Testing
```bash
# Run all tests
python run_tests.py

# Run specific test
python -m pytest tests/test_auth.py -v

# Run with coverage
python run_tests.py --coverage
```

### Database
```bash
# Create migration
alembic revision --autogenerate -m "description"

# Apply migrations
alembic upgrade head
```

## Project Structure
```
app/
├── routers/          # API endpoints
├── templates/        # Jinja2 HTML templates
├── static/          # CSS, JS, uploaded photos
├── models.py        # Database models
├── schemas.py       # Pydantic schemas
├── oauth2.py        # JWT authentication
└── main.py          # FastAPI application
```

## Contributing
Contributions are welcome. Please open an issue or submit a pull request.

## License
MIT License - see LICENSE file for details.

---
*Project inspired by [fastapi-course](https://github.com/Sanjeev-Thiyagarajan/fastapi-course)*

I HATE MY LIFE