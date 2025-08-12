# PhotoRank - Quick Start Guide

## 🚀 One-Command Launch

### Option 1: Automatic Setup (Recommended)
```bash
./setup.sh
```

This script will:
- ✅ Find available ports automatically
- ✅ Clean up conflicting containers
- ✅ Build and start all services
- ✅ Run all database migrations
- ✅ Initialize categories
- ✅ Import existing R2 photos
- ✅ Run health checks
- ✅ Display all access URLs

### Option 2: Simple Launch
```bash
./launch.sh
```

Or specify custom port:
```bash
./launch.sh 8080
```

### Option 3: Manual Docker Compose
```bash
# Set custom ports (optional)
export API_PORT=9001
export DB_PORT=5434

# Start services
docker compose -f docker-compose-dev.yml up --build -d
```

## 🌐 Access URLs
After setup completes, you'll see:
- **Main App**: http://localhost:9001 (or your custom port)
- **Login**: http://localhost:9001/login
- **Leaderboard**: http://localhost:9001/leaderboard
- **Upload**: http://localhost:9001/upload
- **Categories**: http://localhost:9001/categories

## 🔧 Quick Commands

### View Logs
```bash
docker compose -f docker-compose-dev.yml logs -f
```

### Stop Services
```bash
docker compose -f docker-compose-dev.yml down
```

### Restart Services
```bash
docker compose -f docker-compose-dev.yml restart
```

### Check Status
```bash
docker ps
```

## 🐳 Database Access
```bash
# Connect to database
docker exec -it photorank-00e51b570086a0302f6287fa9352c9775ec1d0a7-db-1 psql -U postgres -d fastapi

# Database credentials:
# Host: localhost
# Port: 5434 (or your custom port)
# Database: fastapi
# User: postgres
# Password: pepito1234
```

## 🧪 Testing
```bash
# Run basic tests
docker exec photorank-00e51b570086a0302f6287fa9352c9775ec1d0a7-api-1 python test_basic.py

# Run full test suite
docker exec photorank-00e51b570086a0302f6287fa9352c9775ec1d0a7-api-1 python run_tests.py
```

## 🚨 Troubleshooting

### Port Already in Use
The setup script automatically finds available ports. If you get port conflicts, just run `./setup.sh` again.

### Database Issues
```bash
# Reset database
docker exec photorank-00e51b570086a0302f6287fa9352c9775ec1d0a7-db-1 psql -U postgres -d fastapi -c "DROP SCHEMA public CASCADE; CREATE SCHEMA public;"

# Re-run migrations
docker exec photorank-00e51b570086a0302f6287fa9352c9775ec1d0a7-api-1 alembic upgrade head
```

### R2 Photos Not Showing
The setup script automatically imports existing R2 photos. If needed:
```bash
docker exec photorank-00e51b570086a0302f6287fa9352c9775ec1d0a7-api-1 python import_r2_photos.py
```

### Clean Start
```bash
# Remove everything and start fresh
docker compose -f docker-compose-dev.yml down --volumes --remove-orphans
./setup.sh
```

## 📊 Default Data
After setup, you'll have:
- ✅ 4 categories (paintings, historical-photos, memes, anything)
- ✅ 18 photos from R2 storage
- ✅ All photos ready for voting
- ✅ ELO ranking system active

## 🎯 Ready to Use!
Just run `./setup.sh` and open http://localhost:9001 in your browser!