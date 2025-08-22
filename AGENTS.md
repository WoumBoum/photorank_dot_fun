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

## 🗃️ **Database Access with psql**
Future agents can interact directly with the Supabase PostgreSQL database using psql commands. This is useful for debugging, data analysis, and manual database operations.

### **Prerequisites**
1. **Install psql**: `sudo apt-get install postgresql-client` (Ubuntu/Debian)
2. **Environment Variables**: Ensure `DATABASE_URL` is set in your environment
3. **Network Access**: Ensure you can connect to the Supabase database

### **Basic Connection**
```bash
# Connect to database
psql "$DATABASE_URL"

# Or run a single command
psql "$DATABASE_URL" -c "SELECT version();"
```

### **Common Database Queries**

**Check Database Health:**
```bash
# Check PostgreSQL version
psql "$DATABASE_URL" -c "SELECT version();"

# Check database size
psql "$DATABASE_URL" -c "SELECT pg_size_pretty(pg_database_size(current_database()));"

# Check table sizes
psql "$DATABASE_URL" -c "SELECT schemaname, tablename, pg_size_pretty(pg_total_relation_size(schemaname||'.'||tablename)) as size FROM pg_tables WHERE schemaname = 'public' ORDER BY pg_total_relation_size(schemaname||'.'||tablename) DESC;"
```

**Categories Management:**
```bash
# List all categories
psql "$DATABASE_URL" -c "SELECT id, name, description, created_at FROM categories ORDER BY name;"

# Count photos per category
psql "$DATABASE_URL" -c "SELECT c.name, COUNT(p.id) as photo_count FROM categories c LEFT JOIN photos p ON c.id = p.category_id GROUP BY c.id, c.name ORDER BY photo_count DESC;"

# Find empty categories
psql "$DATABASE_URL" -c "SELECT c.name FROM categories c LEFT JOIN photos p ON c.id = p.category_id WHERE p.id IS NULL;"
```

**Photos Management:**
```bash
# Count total photos
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM photos;"

# Find orphaned photos (photos with deleted categories)
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM photos p LEFT JOIN categories c ON p.category_id = c.id WHERE c.id IS NULL;"

# List orphaned photos with details
psql "$DATABASE_URL" -c "SELECT p.id, p.filename, u.username, p.created_at FROM photos p LEFT JOIN categories c ON p.category_id = c.id LEFT JOIN users u ON p.owner_id = u.id WHERE c.id IS NULL ORDER BY p.created_at DESC LIMIT 10;"

# Clean up orphaned photos
psql "$DATABASE_URL" -c "DELETE FROM photos WHERE id IN (SELECT p.id FROM photos p LEFT JOIN categories c ON p.category_id = c.id WHERE c.id IS NULL);"
```

**Users Management:**
```bash
# Count total users
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM users;"

# List recent users
psql "$DATABASE_URL" -c "SELECT id, username, email, created_at FROM users ORDER BY created_at DESC LIMIT 10;"

# Count photos per user
psql "$DATABASE_URL" -c "SELECT u.username, COUNT(p.id) as photo_count FROM users u LEFT JOIN photos p ON u.id = p.owner_id GROUP BY u.id, u.username ORDER BY photo_count DESC LIMIT 10;"
```

**Votes Management:**
```bash
# Count total votes
psql "$DATABASE_URL" -c "SELECT COUNT(*) FROM votes;"

# Find most active voters
psql "$DATABASE_URL" -c "SELECT u.username, COUNT(v.id) as vote_count FROM users u JOIN votes v ON u.id = v.user_id GROUP BY u.id, u.username ORDER BY vote_count DESC LIMIT 10;"

# Find most voted photos
psql "$DATABASE_URL" -c "SELECT p.filename, COUNT(v.id) as vote_count FROM photos p JOIN votes v ON p.id = v.winner_id OR p.id = v.loser_id GROUP BY p.id, p.filename ORDER BY vote_count DESC LIMIT 10;"
```

### **Foreign Key Constraints**
```bash
# Check all constraints
psql "$DATABASE_URL" -c "SELECT conname, conrelid::regclass, confrelid::regclass, confdeltype FROM pg_constraint WHERE contype = 'f' AND connamespace = 'public'::regnamespace;"

# Check photos category constraint specifically
psql "$DATABASE_URL" -c "SELECT conname, confdeltype FROM pg_constraint WHERE conname = 'photos_category_id_fkey';"
# confdeltype should be 'c' for CASCADE
```

### **Safety Precautions**
- **Always backup before destructive operations**: `pg_dump "$DATABASE_URL" > backup.sql`
- **Test queries first**: Use `SELECT` before `DELETE` or `UPDATE`
- **Use transactions for complex operations**: `BEGIN; ... COMMIT;`
- **Check row counts**: Always verify how many rows will be affected
- **Monitor database size**: Large operations can impact performance

### **Troubleshooting**
```bash
# Check connection
psql "$DATABASE_URL" -c "SELECT 1;"

# Check if database is accessible
psql "$DATABASE_URL" -c "SELECT current_database(), current_user;"

# Check table existence
psql "$DATABASE_URL" -c "SELECT tablename FROM pg_tables WHERE schemaname = 'public';"
```

### **Environment Setup**
```bash
# Set DATABASE_URL (example)
export DATABASE_URL="postgresql://username:password@host:port/database"

# Or use .env file (already configured)
# The application automatically loads DATABASE_URL from environment
```

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

### **Orphaned Photos Management**
When categories are deleted, photos that belonged to those categories can become "orphaned" (still in database but referencing deleted categories). This causes 404 errors in user stats pages.

**Admin Interface**: Available at `/analytics/` for moderators
- View all orphaned photos with thumbnails
- Bulk delete or reassign orphaned photos
- Individual photo management options

**Prevention**: The `fix_photos_category_fk_cascade` migration adds CASCADE deletion to prevent future orphaned photos.

**Manual Cleanup**: If orphaned photos exist, use the admin interface to clean them up.

### Production DB note: boosted_votes
The `boosted_votes` column on `categories` was created manually on Supabase and then stamped in Alembic to keep history aligned.

Do not attempt to re-apply it in production. If you need to align a new environment:
```bash
export DATABASE_URL="postgresql://USER:PASSWORD@HOST:PORT/DBNAME?sslmode=require"
alembic stamp boosted_votes_on_categories
```

Why:
- Render (free) has no post-deploy hook; we used manual SQL + `alembic stamp`.
- New/fresh DBs should still use `alembic upgrade head` to create the column.

Ops:
- Moderator auth relies on `MODERATOR_PROVIDER` and `MODERATOR_PROVIDER_ID`. Set them in Render.

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