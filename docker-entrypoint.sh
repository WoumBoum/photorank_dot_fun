#!/bin/bash
echo "Setting up database..."

# Run comprehensive database setup
python3 /app/setup_database.py

echo "Starting application..."
exec uvicorn app.main:app --host 0.0.0.0 --port $PORT