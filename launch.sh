#!/bin/bash

# PhotoRank - Simple Launch Script
# Usage: ./launch.sh [port]

set -e

# Default ports
DB_PORT=${DB_PORT:-5434}
API_PORT=${API_PORT:-9001}

# Allow custom ports from command line
if [ ! -z "$1" ]; then
    API_PORT=$1
    DB_PORT=$((API_PORT + 3000))  # Offset DB port from API port
fi

# Export ports for docker-compose
export DB_PORT
export API_PORT

echo "🚀 Launching PhotoRank..."
echo "API Port: $API_PORT"
echo "DB Port: $DB_PORT"

# Clean up any existing containers
docker compose -f docker-compose-dev.yml down --remove-orphans 2>/dev/null || true

# Start services
docker compose -f docker-compose-dev.yml up --build -d

echo "⏳ Waiting for services to be ready..."
sleep 10

# Check if services are running
if curl -s http://localhost:$API_PORT/ > /dev/null; then
    echo "✅ PhotoRank is ready!"
    echo "🌐 Open: http://localhost:$API_PORT"
else
    echo "❌ Something went wrong. Check logs with:"
    echo "   docker compose -f docker-compose-dev.yml logs"
fi

echo ""
echo "📋 Quick commands:"
echo "   View logs: docker compose -f docker-compose-dev.yml logs -f"
echo "   Stop:      docker compose -f docker-compose-dev.yml down"
echo "   Restart:   docker compose -f docker-compose-dev.yml restart"