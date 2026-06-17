ALTER TABLE folder_watches ADD COLUMN IF NOT EXISTS generate_derivatives JSON DEFAULT '[]';
