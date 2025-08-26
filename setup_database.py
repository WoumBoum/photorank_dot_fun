#!/usr/bin/env python3
"""Database setup script for PhotoRank"""

import os
import sys
from alembic.config import Config
from alembic import command

def run_migrations():
    """Run Alembic database migrations"""
    try:
        # Get database URL from environment
        database_url = os.environ.get('DATABASE_URL')
        if not database_url:
            print("ERROR: DATABASE_URL environment variable not set")
            sys.exit(1)

        print(f"DEBUG: Using DATABASE_URL: {database_url[:20]}...")

        # Configure Alembic
        alembic_cfg = Config("alembic.ini")
        alembic_cfg.set_main_option("sqlalchemy.url", database_url)

        print("Running database migrations...")
        command.upgrade(alembic_cfg, "head")
        print("Database migrations completed successfully")

    except Exception as e:
        print(f"ERROR: Failed to run migrations: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)

if __name__ == "__main__":
    run_migrations()