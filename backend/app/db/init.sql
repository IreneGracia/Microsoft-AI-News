-- Run once against the Postgres database before app startup.
-- Enables the pgvector extension and creates the vector index that
-- SQLAlchemy create_all can't create on its own.

CREATE EXTENSION IF NOT EXISTS vector;

-- ivfflat index for fast approximate nearest-neighbor search.
-- 100 lists is a reasonable default; tune later if recall is poor.
-- Only created if the articles table already exists (post create_all).
DO $$
BEGIN
    IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_name = 'articles') THEN
        CREATE INDEX IF NOT EXISTS articles_embedding_ivfflat
        ON articles
        USING ivfflat (embedding vector_cosine_ops)
        WITH (lists = 100);
    END IF;
END $$;