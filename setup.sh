#!/bin/bash

# PhotoRank - One-Command Setup Script
# This script handles everything needed for a seamless launch

set -e

echo "🚀 PhotoRank - Complete Setup Script"
echo "======================================"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_status() {
    echo -e "${GREEN}✅ $1${NC}"
}

print_warning() {
    echo -e "${YELLOW}⚠️  $1${NC}"
}

print_error() {
    echo -e "${RED}❌ $1${NC}"
}

print_info() {
    echo -e "${BLUE}ℹ️  $1${NC}"
}

# Check if Docker is running
check_docker() {
    print_info "Checking Docker..."
    if ! docker info > /dev/null 2>&1; then
        print_error "Docker is not running. Please start Docker first."
        exit 1
    fi
    print_status "Docker is running"
}

# Find available ports
find_available_ports() {
    print_info "Finding available ports..."
    
    # Find available database port
    DB_PORT=5434
    while netstat -tuln | grep -q ":$DB_PORT "; do
        DB_PORT=$((DB_PORT + 1))
    done
    
    # Find available API port
    API_PORT=9001
    while netstat -tuln | grep -q ":$API_PORT "; do
        API_PORT=$((API_PORT + 1))
    done
    
    print_status "Using ports: DB=$DB_PORT, API=$API_PORT"
    
    # Update .env file
    sed -i.bak "s/DATABASE_PORT=.*/DATABASE_PORT=$DB_PORT/" .env
    sed -i.bak "s/ports:/ports:/" docker-compose-dev.yml
    sed -i.bak "s/- 5433:5432/- $DB_PORT:5432/" docker-compose-dev.yml
    sed -i.bak "s/- 9001:9000/- $API_PORT:9000/" docker-compose-dev.yml
}

# Clean up existing containers
cleanup_containers() {
    print_info "Cleaning up existing containers..."
    
    # Stop and remove existing containers with conflicting names
    docker compose -f docker-compose-dev.yml down --remove-orphans 2>/dev/null || true
    
    # Remove containers with conflicting ports
    docker ps -a --format "table {{.Names}}\t{{.Ports}}" | grep -E "(5433|5434|9000|9001)" | tail -n +2 | awk '{print $1}' | xargs -r docker stop || true
    docker ps -a --format "table {{.Names}}\t{{.Ports}}" | grep -E "(5433|5434|9000|9001)" | tail -n +2 | awk '{print $1}' | xargs -r docker rm || true
    
    print_status "Cleanup completed"
}

# Build and start services
start_services() {
    print_info "Building and starting services..."
    
    # Build images
    docker compose -f docker-compose-dev.yml build --no-cache
    
    # Start services
    docker compose -f docker-compose-dev.yml up -d
    
    print_status "Services started"
}

# Wait for database to be ready
wait_for_db() {
    print_info "Waiting for database to be ready..."
    
    DB_PORT=$(grep DATABASE_PORT .env | cut -d'=' -f2)
    
    for i in {1..30}; do
        if docker exec photorank-00e51b570086a0302f6287fa9352c9775ec1d0a7-db-1 pg_isready -U postgres > /dev/null 2>&1; then
            print_status "Database is ready"
            return 0
        fi
        echo -n "."
        sleep 2
    done
    
    print_error "Database failed to start"
    exit 1
}

# Run database migrations
run_migrations() {
    print_info "Running database migrations..."
    
    # Reset database if needed
    docker exec photorank-00e51b570086a0302f6287fa9352c9775ec1d0a7-db-1 psql -U postgres -d fastapi -c "DROP SCHEMA IF EXISTS public CASCADE; CREATE SCHEMA public;" || true
    
    # Run migrations in correct order
    docker exec photorank-00e51b570086a0302f6287fa9352c9775ec1d0a7-api-1 alembic upgrade elo_ranking_system
    docker exec photorank-00e51b570086a0302f6287fa9352c9775ec1d0a7-api-1 alembic upgrade add_categories
    
    print_status "Database migrations completed"
}

# Initialize categories
init_categories() {
    print_info "Initializing categories..."
    
    docker exec photorank-00e51b570086a0302f6287fa9352c9775ec1d0a7-api-1 python -c "
import sys
sys.path.append('/usr/src/app')
from app.database import SessionLocal
from app.models import Category

db = SessionLocal()
categories = [
    {'name': 'paintings', 'description': 'Paintings and artwork'},
    {'name': 'historical-photos', 'description': 'Historical photographs'},
    {'name': 'memes', 'description': 'Internet memes and humorous content'},
    {'name': 'anything', 'description': 'Anything else'}
]

for cat_data in categories:
    existing = db.query(Category).filter(Category.name == cat_data['name']).first()
    if not existing:
        cat = Category(**cat_data)
        db.add(cat)

db.commit()
db.close()
print('Categories initialized')
"
    
    print_status "Categories initialized"
}

# Import existing R2 photos
import_r2_photos() {
    print_info "Importing existing R2 photos..."
    
    docker exec photorank-00e51b570086a0302f6287fa9352c9775ec1d0a7-api-1 python import_r2_photos.py
    
    print_status "R2 photos imported"
}

# Run health checks
health_check() {
    print_info "Running health checks..."
    
    API_PORT=$(grep -A 10 "ports:" docker-compose-dev.yml | grep -o "[0-9]*:9000" | cut -d':' -f1)
    
    # Wait for API to be ready
    for i in {1..30}; do
        if curl -s http://localhost:$API_PORT/ > /dev/null; then
            print_status "API is responding"
            break
        fi
        echo -n "."
        sleep 2
    done
    
    # Test basic functionality
    docker exec photorank-00e51b570086a0302f6287fa9352c9775ec1d0a7-api-1 python test_basic.py
    
    print_status "Health checks passed"
}

# Display final information
display_info() {
    API_PORT=$(grep -A 10 "ports:" docker-compose-dev.yml | grep -o "[0-9]*:9000" | cut -d':' -f1)
    DB_PORT=$(grep -A 5 "ports:" docker-compose-dev.yml | grep -o "[0-9]*:5432" | cut -d':' -f1)
    
    echo ""
    echo "🎉 PhotoRank Setup Complete!"
    echo "============================"
    echo ""
    echo "🌐 Application URLs:"
    echo "   Main App:    http://localhost:$API_PORT"
    echo "   Login:       http://localhost:$API_PORT/login"
    echo "   Leaderboard: http://localhost:$API_PORT/leaderboard"
    echo "   Upload:      http://localhost:$API_PORT/upload"
    echo "   Categories:  http://localhost:$API_PORT/categories"
    echo ""
    echo "🐳 Docker Services:"
    echo "   API:    photorank-00e51b570086a0302f6287fa9352c9775ec1d0a7-api-1"
    echo "   DB:     photorank-00e51b570086a0302f6287fa9352c9775ec1d0a7-db-1"
    echo ""
    echo "📊 Database:"
    echo "   Port:     $DB_PORT"
    echo "   Name:     fastapi"
    echo "   User:     postgres"
    echo "   Password: pepito1234"
    echo ""
    echo "🔧 Quick Commands:"
    echo "   View logs: docker compose -f docker-compose-dev.yml logs -f"
    echo "   Stop:      docker compose -f docker-compose-dev.yml down"
    echo "   Restart:   docker compose -f docker-compose-dev.yml restart"
    echo ""
    echo "✅ All systems ready! Open http://localhost:$API_PORT to start using PhotoRank"
}

# Main execution
main() {
    echo "Starting PhotoRank setup..."
    
    check_docker
    find_available_ports
    cleanup_containers
    start_services
    wait_for_db
    run_migrations
    init_categories
    import_r2_photos
    health_check
    display_info
}

# Handle script interruption
trap 'print_error "Setup interrupted"; exit 1' INT TERM

# Run main function
main