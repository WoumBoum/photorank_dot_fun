# PhotoRank - Agent Guide

Welcome to PhotoRank! This document serves as the definitive guide for all future agents working on this project. Read this carefully before making any changes.

## 🎯 **Project Vision & Purpose**

**PhotoRank** is an ultra-minimalist, brutalist photo ranking application that uses the ELO rating system to rank photos through direct comparison voting. The app embodies the philosophy of "less is more" - no captions, no comments, no likes, just pure aesthetic judgment.

### **Core Philosophy**
- **Brutalist Design**: White/off-white background, sharp black typography, 1-pixel light-gray dividers
- **Anti-creep**: No social features, no engagement farming
- **Quality over Quantity**: 50 duel minimum for leaderboard eligibility
- **Rate Limiting**: 5 uploads per 24 hours to prevent spam

## 🏗️ **Architecture Overview**

### **Tech Stack**
- **Backend**: FastAPI (Python 3.9) with PostgreSQL
- **Frontend**: Jinja2 templates with ultra-minimalist CSS
- **Database**: PostgreSQL with optimized schema for ELO calculations
- **Authentication**: OAuth2 (GitHub/Google) with JWT tokens
- **Real-time**: WebSocket for live updates

### **Database Schema**
```sql
users: id, email, username, provider, provider_id, created_at
photos: id, filename, elo_rating, total_duels, wins, owner_id, created_at
votes: id, user_id, winner_id, loser_id, created_at
upload_limits: user_id, upload_count, last_upload_date
```

### **Key Relationships**
- **User → Photos**: One-to-many (owner)
- **User → Votes**: One-to-many (voter)
- **Photos → Votes**: Many-to-many through winner/loser
- **User → UploadLimits**: One-to-one (rate limiting)

## 🎨 **Design System**

### **Brutalist Design Principles**
- **Colors**: White/off-white background (#fafafa), pure black text (#000), light-gray dividers (#e0e0e0)
- **Typography**: 'Courier New' monospace, sharp and clean
- **Layout**: Maximum 1200px container, generous spacing
- **Interactions**: 250ms fade transitions, no animations beyond functional
- **Icons**: Only crown emoji (👑) in leaderboard, nothing else

### **Responsive Design**
- **Desktop**: Side-by-side photo comparison
- **Mobile**: Stacked layout with same functionality
- **Breakpoints**: 768px for mobile optimization

## ⚡ **Core Features & Flows**

### **1. Authentication Flow**
```
User → /login → Choose OAuth → GitHub/Google → Callback → JWT Token → App Access
```

### **2. Photo Upload Flow**
```
User → /upload → Drag/Drop or Click → Rate Limit Check → Save → ELO=1200 → Return
```

### **3. Voting Flow**
```
User → / → See 2 Photos → Click Choice → 250ms Fade → ELO Update → New Pair
```

### **4. Leaderboard Flow**
```
User → /leaderboard → Top 100 Photos → Crown Icons → Hover for Details
```

## 📊 **ELO Rating System**

### **Algorithm Details**
- **K-Factor**: 32 (moderate sensitivity)
- **Initial Rating**: 1200
- **Formula**: `new_rating = old_rating + K * (actual - expected)`
- **Expected Score**: `1 / (1 + 10^((opponent_rating - current_rating)/400))`

### **Eligibility Rules**
- **Leaderboard**: ≥50 duels fought
- **Ranking**: Sorted by ELO descending
- **Display**: Top 100 photos maximum

## 🔒 **Security & Rate Limiting**

### **Upload Limits**
- **Daily**: 5 photos per user
- **Reset**: 24 hours from last upload
- **Tracking**: Per-user via upload_limits table

### **Authentication**
- **Method**: OAuth2 (GitHub/Google)
- **Tokens**: JWT with 30-minute expiration
- **Storage**: URL parameter for frontend access

## 🗂️ **Project Structure**

```
app/
├── routers/
│   ├── auth.py          # OAuth + JWT
│   ├── photos.py        # Upload + retrieval
│   ├── votes.py         # ELO calculations
│   └── websocket.py     # Real-time updates
├── templates/           # Jinja2 HTML
├── static/
│   ├── css/style.css    # Brutalist CSS
│   └── js/app.js        # Frontend logic
├── models.py            # Database models
├── schemas.py           # Pydantic schemas
├── oauth2.py            # JWT handling
└── main.py              # FastAPI app
```

## 🧪 **Testing Guidelines**

### **Test Categories**
1. **Unit Tests**: ELO calculations, JWT tokens
2. **Integration Tests**: Complete user workflows
3. **Edge Cases**: Boundary conditions, error handling
4. **Performance**: Large datasets, concurrent operations

### **Key Test Commands**
```bash
# Basic functionality
python test_basic.py

# Full test suite
python run_tests.py

# With coverage
python run_tests.py --coverage
```

## 🚀 **Development Workflow**

### **Environment Setup**
```bash
# Start development environment
docker compose -f docker-compose-dev.yml up -d

# Access app
http://localhost:9001

# Database access
psql -h localhost -p 5433 -U postgres -d fastapi_test
```

### **Making Changes**
1. **Always test**: Run `python test_basic.py` before committing
2. **Follow design**: Maintain brutalist aesthetic
3. **Preserve simplicity**: No new features without strong justification
4. **Test edge cases**: Especially rate limiting and ELO calculations

## 🛠️ **Build/Lint/Test Commands**

### **Quick Commands**
```bash
# Single test: python tests/test_auth.py::test_login
python -m pytest tests/test_auth.py -v

# All tests: python run_tests.py
python test_basic.py  # Core functionality
python run_tests.py --coverage  # With coverage

# Lint/format: autopep8 --in-place --aggressive app/*.py
autopep8 --in-place --aggressive app/routers/*.py
```

### **Development Setup**
```bash
docker compose -f docker-compose-dev.yml up -d  # Start dev env
psql -h localhost -p 5433 -U postgres -d fastapi_test  # DB access
```

## 🎨 **Code Style Guidelines**

### **Imports & Types**
- Use type hints for all functions
- Import order: stdlib → third-party → local
- Use `from typing import Optional, List, Dict`

### **Naming & Formatting**
- snake_case for variables/functions
- PascalCase for classes
- UPPER_SNAKE_CASE for constants
- 79 char line limit, 4-space indentation

### **Error Handling**
- Use FastAPI HTTPException with specific status codes
- Always validate input with Pydantic schemas
- Log errors with context: `logger.error(f"Failed to {action}: {error}")`

### **Database & Security**
- Use SQLAlchemy ORM, never raw SQL
- Always use parameterized queries
- Validate file uploads: size, type, dimensions
- JWT tokens: 30min expiry, secure HTTP-only cookies

## 📋 **Common Tasks**

### **Database Migrations**
```bash
alembic revision --autogenerate -m "description"
alembic upgrade head
```

### **Testing**
```bash
# Create migration: alembic revision --autogenerate -m "description"
# Test migration: alembic upgrade head
# Verify: Run all tests
```

### **OAuth Setup**
1. **GitHub**: https://github.com/settings/developers
2. **Google**: https://console.developers.google.com/
3. **Redirect URLs**: `http://localhost:9001/auth/callback/{provider}`

## ⚠️ **Important Notes**

### **Design Constraints**
- **Never add**: Comments, likes, follows, or social features
- **Never change**: Brutalist design aesthetic
- **Never remove**: Rate limiting or ELO system
- **Always maintain**: 50 duel minimum for leaderboard

### **Performance Considerations**
- **Database**: Use indexes on frequently queried columns
- **Caching**: Consider Redis for leaderboard if scaling
- **Images**: Optimize uploads, consider CDN for production

### **Security Checklist**
- [ ] Rate limiting active
- [ ] JWT tokens properly validated
- [ ] File upload restrictions enforced
- [ ] SQL injection prevention
- [ ] XSS protection via templates

## 📞 **Support & Resources**

### **Quick Commands**
```bash
# Check status
docker compose -f docker-compose-dev.yml ps

# View logs
docker compose -f docker-compose-dev.yml logs api

# Restart
docker compose -f docker-compose-dev.yml restart

# Clean restart
docker compose -f docker-compose-dev.yml down && docker compose -f docker-compose-dev.yml up -d
```

### **Key URLs**
- **App**: http://localhost:9001
- **Login**: http://localhost:9001/login
- **Upload**: http://localhost:9001/upload
- **Leaderboard**: http://localhost:9001/leaderboard
- **Stats**: http://localhost:9001/stats

### **Recent Changes Location**
- **Upload limit**: `app/routers/photos.py:91` (change `>= 5` to desired number)
- **Delete endpoint**: `app/routers/photos.py:149-183`
- **Stats endpoint**: `app/routers/users.py:13-52`
- **Image sizing**: `app/static/css/style.css` (lines 84-89, 114-119, 185-190)
- **Text alignment**: `app/static/css/style.css` (lines 175-210)

---
**Remember**: This app is intentionally minimal. Every change should enhance the core experience without adding complexity. When in doubt, choose simplicity over features.

## ✅ **Deployment Status**
**Current Status**: ✅ **WORKING** - Successfully deployed and functional
- **Database**: Complete schema with all tables (users, photos, votes, upload_limits, categories)
- **Authentication**: OAuth2 (GitHub/Google) working correctly
- **Core Features**: Photo upload, voting, ELO ranking, leaderboard all operational
- **Rate Limiting**: 5 uploads per 24 hours enforced
- **Known Issues**: Minimal - occasional 500 errors on categories endpoint resolved

**Last Updated**: July 2025 by Agent Kimi - PhotoRank Creator
**Major Updates**: Complete database setup fix, deployment stabilization, working production version
**Deployment**: Render.com + Supabase PostgreSQL - Fully functional