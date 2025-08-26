#!/bin/bash

# Set default port if not provided
PORT=${PORT:-10000}

echo "Setting up database..."

# Run database migrations if setup script exists
if [ -f "/app/setup_database.py" ]; then
    python3 /app/setup_database.py
else
    echo "WARNING: setup_database.py not found, running alembic directly..."
    # Fallback: try to run alembic directly
    if command -v alembic &> /dev/null; then
        alembic upgrade head
    else
        echo "ERROR: Neither setup_database.py nor alembic command found"
        exit 1
    fi
fi

echo "Starting application on port $PORT..."
exec uvicorn app.main:app --host 0.0.0.0 --port $PORT