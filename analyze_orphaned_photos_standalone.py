#!/usr/bin/env python
"""
Standalone script to analyze orphaned photos (photos with deleted categories)
This script can be run independently to check the current state of the database.
"""

import psycopg2
import os
from datetime import datetime

def get_database_url():
    """Get database URL from environment"""
    return os.getenv('DATABASE_URL', 'postgresql://postgres:password@localhost:5432/photorank')

def analyze_orphaned_photos():
    """Analyze photos that belong to deleted categories"""
    try:
        # Connect to database
        conn = psycopg2.connect(get_database_url())
        cursor = conn.cursor()

        print("=== Orphaned Photos Analysis ===\n")

        # Find orphaned photos
        query = """
        SELECT p.id, p.filename, p.elo_rating, p.total_duels, p.wins,
               p.owner_id, p.category_id, p.created_at,
               u.username as owner_username
        FROM photos p
        LEFT JOIN categories c ON p.category_id = c.id
        LEFT JOIN users u ON p.owner_id = u.id
        WHERE c.id IS NULL
        ORDER BY p.created_at DESC
        """

        cursor.execute(query)
        orphaned_photos = cursor.fetchall()

        print(f"Found {len(orphaned_photos)} orphaned photos:\n")

        if orphaned_photos:
            print("ID | Filename | Owner | ELO | Duels | Wins | Category ID | Created")
            print("-" * 80)

            for photo in orphaned_photos:
                (photo_id, filename, elo_rating, total_duels, wins,
                 owner_id, category_id, created_at, owner_username) = photo

                print(f"{photo_id} | {filename[:20]}... | {owner_username or 'unknown'} | {elo_rating:.0f} | {total_duels} | {wins} | {category_id} | {created_at.strftime('%Y-%m-%d')}")

            print(f"\nTotal orphaned photos: {len(orphaned_photos)}")

            # Get some statistics
            cursor.execute("SELECT COUNT(*) FROM photos")
            total_photos = cursor.fetchone()[0]

            cursor.execute("SELECT COUNT(*) FROM categories")
            total_categories = cursor.fetchone()[0]

            print(f"Total photos in database: {total_photos}")
            print(f"Total categories in database: {total_categories}")
            print(".1f")

        else:
            print("No orphaned photos found!")

        # Check foreign key constraint
        print("\n=== Foreign Key Constraint Check ===")
        cursor.execute("""
            SELECT conname, conrelid::regclass, confrelid::regclass, conkey, confkey, confdeltype
            FROM pg_constraint
            WHERE conname = 'photos_category_id_fkey'
        """)

        constraint = cursor.fetchone()
        if constraint:
            confdeltype = constraint[5]
            if confdeltype == 'c':  # CASCADE
                print("✓ Foreign key constraint has CASCADE on delete")
            else:
                print("⚠ Foreign key constraint does NOT have CASCADE on delete")
                print("   This means photos won't be automatically deleted when categories are deleted")
        else:
            print("⚠ No foreign key constraint found for photos.category_id")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"Error analyzing orphaned photos: {e}")

def generate_cleanup_sql():
    """Generate SQL to clean up orphaned photos"""
    try:
        conn = psycopg2.connect(get_database_url())
        cursor = conn.cursor()

        # Get orphaned photos
        cursor.execute("""
            SELECT p.id, p.filename
            FROM photos p
            LEFT JOIN categories c ON p.category_id = c.id
            WHERE c.id IS NULL
        """)

        orphaned_photos = cursor.fetchall()

        if orphaned_photos:
            print("\n=== Cleanup SQL Generated ===")
            print("-- This SQL will delete all orphaned photos and their associated votes")
            print("-- Run this in your database to clean up orphaned photos")
            print()

            photo_ids = [photo[0] for photo in orphaned_photos]

            # Generate DELETE statements
            print("-- Delete orphaned photos")
            for photo_id in photo_ids:
                print(f"DELETE FROM photos WHERE id = {photo_id};")

            print()
            print("-- Alternative: Delete all orphaned photos at once")
            print(f"DELETE FROM photos WHERE id IN ({', '.join(map(str, photo_ids))});")

            print(f"\n-- Total orphaned photos to delete: {len(photo_ids)}")

        cursor.close()
        conn.close()

    except Exception as e:
        print(f"Error generating cleanup SQL: {e}")

if __name__ == "__main__":
    print("Orphaned Photos Analysis Tool")
    print("=============================")

    analyze_orphaned_photos()
    generate_cleanup_sql()

    print("\n=== Next Steps ===")
    print("1. Review the orphaned photos list above")
    print("2. If you want to delete them, run the generated SQL")
    print("3. After cleanup, run the migration to add CASCADE constraint:")
    print("   alembic upgrade fix_photos_category_fk_cascade")
    print("4. Access the admin interface at: /admin/orphaned-photos")