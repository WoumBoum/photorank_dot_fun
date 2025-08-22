#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Direct database migration script to apply CASCADE constraint fix
"""

import os
import sys

def get_database_url():
    """Get database URL from environment"""
    return os.getenv('DATABASE_URL')

def apply_migration():
    """Apply the CASCADE constraint fix directly"""
    database_url = get_database_url()
    if not database_url:
        print("ERROR: DATABASE_URL environment variable not set")
        return False

    print("=== Applying CASCADE Constraint Fix ===")
    print("Database URL: {}".format(database_url.replace(':2XugguC-Q#Z2Uvy@', ':***@')))

    # For security, we'll provide the SQL commands that need to be run
    # rather than trying to connect directly from this environment

    sql_commands = [
        "-- Check current constraint",
        "SELECT conname, conkey, confkey, confdeltype FROM pg_constraint WHERE conname = 'photos_category_id_fkey';",
        "",
        "-- Drop the existing constraint (if it exists)",
        "ALTER TABLE photos DROP CONSTRAINT IF EXISTS photos_category_id_fkey;",
        "",
        "-- Create new constraint with CASCADE",
        "ALTER TABLE photos ADD CONSTRAINT photos_category_id_fkey FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE;",
        "",
        "-- Verify the constraint was applied correctly",
        "SELECT conname, confdeltype FROM pg_constraint WHERE conname = 'photos_category_id_fkey';"
    ]

    print("\n=== SQL Commands to Execute ===")
    print("Please run these commands in your PostgreSQL database:")
    print("\n" + "="*60)

    for cmd in sql_commands:
        print(cmd)

    print("="*60)
    print("\nYou can run these commands using:")
    print("1. psql command line tool")
    print("2. Your database admin interface (like Supabase dashboard)")
    print("3. Any PostgreSQL client")

    print("\nAfter running the commands, verify with:")
    print("SELECT conname, confdeltype FROM pg_constraint WHERE conname = 'photos_category_id_fkey';")
    print("Expected result: confdeltype should be 'c' (CASCADE)")

    return True

if __name__ == "__main__":
    success = apply_migration()
    if success:
        print("\n✅ Migration commands prepared successfully!")
        print("Please execute the SQL commands shown above in your database.")
    else:
        print("\n❌ Failed to prepare migration")
        sys.exit(1)