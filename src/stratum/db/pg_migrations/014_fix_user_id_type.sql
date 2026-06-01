-- Standardise user_id to TEXT across all service-layer tables.
-- The notes/substrate/concepts tables already use TEXT; align the rest.
ALTER TABLE views         ALTER COLUMN user_id TYPE TEXT USING user_id::TEXT;
ALTER TABLE highlights    ALTER COLUMN user_id TYPE TEXT USING user_id::TEXT;
ALTER TABLE subscriptions ALTER COLUMN user_id TYPE TEXT USING user_id::TEXT;
ALTER TABLE recommendations  ALTER COLUMN user_id TYPE TEXT USING user_id::TEXT;
ALTER TABLE changefeed       ALTER COLUMN user_id TYPE TEXT USING user_id::TEXT;
