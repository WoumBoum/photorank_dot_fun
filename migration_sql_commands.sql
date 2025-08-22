-- SQL commands to apply the CASCADE constraint fix
-- Run these commands directly in your PostgreSQL database

-- Step 1: Check current constraint
SELECT conname, conkey, confkey, confdeltype
FROM pg_constraint
WHERE conname = 'photos_category_id_fkey';

-- Step 2: Drop the existing constraint (if it exists)
ALTER TABLE photos DROP CONSTRAINT IF EXISTS photos_category_id_fkey;

-- Step 3: Create new constraint with CASCADE
ALTER TABLE photos
ADD CONSTRAINT photos_category_id_fkey
FOREIGN KEY (category_id) REFERENCES categories(id) ON DELETE CASCADE;

-- Step 4: Verify the constraint was applied correctly
SELECT conname, confdeltype
FROM pg_constraint
WHERE conname = 'photos_category_id_fkey';

-- Expected result: confdeltype should be 'c' (CASCADE)
-- If confdeltype is 'c', the migration was successful!