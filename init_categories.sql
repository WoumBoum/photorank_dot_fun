-- Create categories table if it doesn't exist
CREATE TABLE IF NOT EXISTS categories (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255) UNIQUE NOT NULL,
    description TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Insert the 4 default categories
INSERT INTO categories (name, description) VALUES 
('paintings', 'Paintings and artwork'),
('historical-photos', 'Historical photographs'),
('memes', 'Internet memes and humorous content'),
('anything', 'Anything else')
ON CONFLICT (name) DO NOTHING;

-- Add category_id to photos table if it doesn't exist
ALTER TABLE photos 
ADD COLUMN IF NOT EXISTS category_id INTEGER,
ADD CONSTRAINT fk_photos_category 
    FOREIGN KEY (category_id) REFERENCES categories(id) 
    ON DELETE SET NULL;