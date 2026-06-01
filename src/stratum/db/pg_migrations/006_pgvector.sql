-- pgvector extension + embedding column.
-- Requires pgvector to be installed in the PostgreSQL server
-- (use pgvector/pgvector:pg16 docker image instead of plain postgres:16-alpine).
-- This migration is a no-op if pgvector is not available.

DO $$
BEGIN
    BEGIN
        CREATE EXTENSION IF NOT EXISTS vector;
    EXCEPTION
        WHEN OTHERS THEN
            RAISE NOTICE 'pgvector not available (%), skipping embedding column + index.', SQLERRM;
            RETURN;
    END;

    -- Add embedding column if pgvector loaded successfully
    IF EXISTS (
        SELECT 1 FROM information_schema.tables
        WHERE table_name = 'platform_content_chunk'
    ) THEN
        EXECUTE '
            ALTER TABLE platform_content_chunk
            ADD COLUMN IF NOT EXISTS embedding vector(1024)
        ';
        EXECUTE '
            CREATE INDEX IF NOT EXISTS idx_chunk_embedding
            ON platform_content_chunk
            USING ivfflat (embedding vector_cosine_ops)
            WITH (lists = 100)
        ';
    END IF;
END $$;
