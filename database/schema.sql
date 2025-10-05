-- Schéma PostgreSQL avec PGVector pour RAG
-- Adapté pour embeddings de dimension 1024 (multilingual-e5-large)

CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Supprimer les tables existantes si nécessaire
DROP TABLE IF EXISTS chunks CASCADE;
DROP TABLE IF EXISTS documents CASCADE;
DROP INDEX IF EXISTS idx_chunks_embedding;
DROP INDEX IF EXISTS idx_chunks_document_id;
DROP INDEX IF EXISTS idx_documents_metadata;

-- Table des documents sources
CREATE TABLE documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX idx_documents_metadata ON documents USING GIN (metadata);
CREATE INDEX idx_documents_created_at ON documents (created_at DESC);

-- Table des chunks avec embeddings (dimension 1024)
CREATE TABLE chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    embedding vector(1024),  -- Modifié de 1536 à 1024 pour multilingual-e5-large
    chunk_index INTEGER NOT NULL,
    metadata JSONB DEFAULT '{}',
    token_count INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Index pour la recherche vectorielle (IVFFlat pour performance)
CREATE INDEX idx_chunks_embedding ON chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX idx_chunks_document_id ON chunks (document_id);
CREATE INDEX idx_chunks_chunk_index ON chunks (document_id, chunk_index);

-- Fonction de recherche par similarité cosinus
CREATE OR REPLACE FUNCTION match_chunks(
    query_embedding vector(1024),  -- Modifié de 1536 à 1024
    match_count INT DEFAULT 10,
    similarity_threshold FLOAT DEFAULT 0.0
)
RETURNS TABLE (
    id UUID,
    document_id UUID,
    content TEXT,
    similarity FLOAT,
    metadata JSONB,
    document_title TEXT,
    document_source TEXT
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id,
        c.document_id,
        c.content,
        1 - (c.embedding <=> query_embedding) AS similarity,
        c.metadata,
        d.title AS document_title,
        d.source AS document_source
    FROM chunks c
    JOIN documents d ON c.document_id = d.id
    WHERE c.embedding IS NOT NULL
        AND (1 - (c.embedding <=> query_embedding)) >= similarity_threshold
    ORDER BY c.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Fonction pour mettre à jour automatiquement updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Trigger pour mettre à jour updated_at automatiquement
CREATE TRIGGER update_documents_updated_at BEFORE UPDATE ON documents
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Statistiques et informations
COMMENT ON TABLE documents IS 'Documents sources ingérés dans le système RAG';
COMMENT ON TABLE chunks IS 'Chunks de texte avec embeddings pour recherche vectorielle';
COMMENT ON COLUMN chunks.embedding IS 'Vecteur d''embedding de dimension 1024 (multilingual-e5-large)';
COMMENT ON FUNCTION match_chunks IS 'Recherche de chunks par similarité cosinus avec seuil optionnel';
