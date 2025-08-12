# Category Feature Implementation

This document describes the implementation of the category feature for PhotoRank.

## Overview

The category feature allows users to organize photos into different categories and filter content by category across the application.

## Categories

The following categories are available:
- **paintings** - Paintings and artwork
- **historical-photos** - Historical photographs
- **memes** - Internet memes and humorous content
- **anything** - Anything else (default)

## Database Changes

### New Tables
- `categories` - Stores category information
- Updated `photos` table with `category_id` foreign key

### Schema
```sql
CREATE TABLE categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR NOT NULL UNIQUE,
    description VARCHAR,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

ALTER TABLE photos ADD COLUMN category_id INTEGER NOT NULL;
ALTER TABLE photos ADD CONSTRAINT photos_category_id_fkey 
    FOREIGN KEY (category_id) REFERENCES categories(id);
```

## API Endpoints

### New Endpoints
- `GET /api/categories` - List all categories
- `GET /api/categories/{id}` - Get specific category

### Updated Endpoints
- `GET /api/photos/pair?category_id={id}` - Get random photos for voting, filtered by category
- `GET /api/photos/leaderboard?category_id={id}` - Get leaderboard, filtered by category
- `POST /api/photos/upload` - Now requires `category_id` parameter

## UI Changes

### Upload Page
- Added category dropdown selector before upload
- Users must select a category before uploading

### Leaderboard Page
- Added category filter dropdown
- Users can filter leaderboard by category

### Voting Page
- Added category selector
- Users can choose which category to vote on

## Setup Instructions

1. **Run the migration**:
   ```bash
   python3 manual_migration.py
   ```

2. **Initialize categories** (if not done by migration):
   ```bash
   python3 init_categories.py
   ```

3. **Restart the application**:
   ```bash
   docker compose -f docker-compose-dev.yml restart
   ```

## Usage

### Uploading Photos
1. Go to `/upload`
2. Select a category from the dropdown
3. Upload your photo

### Filtering Leaderboard
1. Go to `/leaderboard`
2. Use the category dropdown to filter results

### Voting by Category
1. Go to `/`
2. Use the category selector to choose which category to vote on
3. Vote on photos from the selected category

## Technical Notes

- All existing photos are automatically assigned to the "anything" category
- Category selection is required for new uploads
- Category filtering works across all relevant endpoints
- The UI maintains the brutalist design aesthetic
- Category IDs are hardcoded in the frontend for simplicity (1-4)

## Future Enhancements

- Dynamic category creation by users
- Category-specific upload limits
- Category statistics and analytics
- Category-specific leaderboards with separate ELO rankings