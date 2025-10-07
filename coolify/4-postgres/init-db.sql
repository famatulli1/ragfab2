-- ============================================================================
-- RAGFab - Script d'initialisation complet PostgreSQL
-- Fusion de schema.sql + 02_web_schema.sql
-- Exécuté automatiquement au premier démarrage du container
-- ============================================================================

-- Extensions nécessaires
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- SCHEMA RAG (Documents et Chunks)
-- ============================================================================

-- Table des documents sources
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title TEXT NOT NULL,
    source TEXT NOT NULL,
    content TEXT NOT NULL,
    metadata JSONB DEFAULT '{}',
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_documents_metadata ON documents USING GIN (metadata);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents (created_at DESC);

-- Table des chunks avec embeddings (dimension 1024)
CREATE TABLE IF NOT EXISTS chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    content TEXT NOT NULL,
    embedding vector(1024),  -- multilingual-e5-large
    chunk_index INTEGER NOT NULL,
    metadata JSONB DEFAULT '{}',
    token_count INTEGER,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(document_id, chunk_index)
);

-- Index pour recherche vectorielle rapide
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON chunks USING ivfflat (embedding vector_cosine_ops) WITH (lists = 100);
CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks (document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_chunk_index ON chunks (document_id, chunk_index);

-- Fonction de recherche par similarité cosinus
CREATE OR REPLACE FUNCTION match_chunks(
    query_embedding vector(1024),
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

-- ============================================================================
-- SCHEMA WEB (Authentification, Conversations, Messages)
-- ============================================================================

-- Table des utilisateurs admin
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(255) UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    email VARCHAR(255),
    is_active BOOLEAN DEFAULT true,
    is_admin BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- Table des conversations
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(500) DEFAULT 'Nouvelle conversation',
    provider VARCHAR(50) NOT NULL DEFAULT 'mistral',
    use_tools BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    message_count INTEGER DEFAULT 0,
    archived BOOLEAN DEFAULT false
);

CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON conversations(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversations_updated_at ON conversations(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);

-- Table des messages
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,
    content TEXT NOT NULL,
    sources JSONB,
    provider VARCHAR(50),
    model_name VARCHAR(100),
    token_usage JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_regenerated BOOLEAN DEFAULT false,
    parent_message_id UUID REFERENCES messages(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);
CREATE INDEX IF NOT EXISTS idx_messages_role ON messages(role);

-- Table des notations de messages
CREATE TABLE IF NOT EXISTS message_ratings (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    message_id UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    rating SMALLINT NOT NULL CHECK (rating IN (-1, 1)),
    feedback TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(message_id)
);

CREATE INDEX IF NOT EXISTS idx_message_ratings_message_id ON message_ratings(message_id);
CREATE INDEX IF NOT EXISTS idx_message_ratings_rating ON message_ratings(rating);

-- Table des jobs d'ingestion
CREATE TABLE IF NOT EXISTS ingestion_jobs (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    filename VARCHAR(500) NOT NULL,
    file_size BIGINT,
    status VARCHAR(50) NOT NULL DEFAULT 'pending',
    progress INTEGER DEFAULT 0,
    document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
    chunks_created INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE
);

CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_status ON ingestion_jobs(status);
CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_created_at ON ingestion_jobs(created_at DESC);

-- ============================================================================
-- FUNCTIONS ET TRIGGERS
-- ============================================================================

-- Fonction pour mettre à jour updated_at
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger pour documents
DROP TRIGGER IF EXISTS update_documents_updated_at ON documents;
CREATE TRIGGER update_documents_updated_at
    BEFORE UPDATE ON documents
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Trigger pour conversations
DROP TRIGGER IF EXISTS update_conversations_updated_at ON conversations;
CREATE TRIGGER update_conversations_updated_at
    BEFORE UPDATE ON conversations
    FOR EACH ROW
    EXECUTE FUNCTION update_updated_at_column();

-- Fonction pour incrémenter le compteur de messages
CREATE OR REPLACE FUNCTION increment_message_count()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE conversations
    SET message_count = message_count + 1,
        updated_at = CURRENT_TIMESTAMP
    WHERE id = NEW.conversation_id;
    RETURN NEW;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS increment_conversation_message_count ON messages;
CREATE TRIGGER increment_conversation_message_count
    AFTER INSERT ON messages
    FOR EACH ROW
    EXECUTE FUNCTION increment_message_count();

-- Fonction pour décrémenter le compteur de messages
CREATE OR REPLACE FUNCTION decrement_message_count()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE conversations
    SET message_count = GREATEST(0, message_count - 1),
        updated_at = CURRENT_TIMESTAMP
    WHERE id = OLD.conversation_id;
    RETURN OLD;
END;
$$ language 'plpgsql';

DROP TRIGGER IF EXISTS decrement_conversation_message_count ON messages;
CREATE TRIGGER decrement_conversation_message_count
    AFTER DELETE ON messages
    FOR EACH ROW
    EXECUTE FUNCTION decrement_message_count();

-- ============================================================================
-- VUES
-- ============================================================================

-- Vue conversation_stats
DROP VIEW IF EXISTS conversation_stats;
CREATE VIEW conversation_stats AS
SELECT
    c.id,
    c.title,
    c.provider,
    c.use_tools,
    c.created_at,
    c.updated_at,
    c.message_count,
    c.archived,
    COUNT(DISTINCT m.id) AS actual_message_count,
    COUNT(DISTINCT mr.id) FILTER (WHERE mr.rating = 1) AS thumbs_up_count,
    COUNT(DISTINCT mr.id) FILTER (WHERE mr.rating = -1) AS thumbs_down_count
FROM conversations c
LEFT JOIN messages m ON c.id = m.conversation_id
LEFT JOIN message_ratings mr ON m.id = mr.message_id
GROUP BY c.id, c.title, c.provider, c.use_tools, c.created_at, c.updated_at, c.message_count, c.archived;

-- Vue document_stats
DROP VIEW IF EXISTS document_stats;
CREATE VIEW document_stats AS
SELECT
    d.id,
    d.title,
    d.source,
    d.created_at,
    COUNT(c.id) AS chunk_count,
    SUM(LENGTH(c.content)) AS total_content_length,
    AVG(c.token_count) AS avg_chunk_tokens
FROM documents d
LEFT JOIN chunks c ON d.id = c.document_id
GROUP BY d.id, d.title, d.source, d.created_at;

-- ============================================================================
-- SEED DATA
-- ============================================================================

-- Utilisateur admin par défaut (username: admin, password: admin)
INSERT INTO users (username, hashed_password, email, is_admin, is_active)
VALUES (
    'admin',
    '$2b$12$1bs.lMmsO5iuv3.fP7oU3eNCspUfHUPeyOKUXx3mZKTdLu/vsYurq',
    'admin@ragfab.local',
    true,
    true
)
ON CONFLICT (username) DO NOTHING;

-- ============================================================================
-- COMMENTAIRES
-- ============================================================================

COMMENT ON TABLE documents IS 'Documents sources ingérés dans le système RAG';
COMMENT ON TABLE chunks IS 'Chunks vectorisés avec embeddings 1024D (multilingual-e5-large)';
COMMENT ON TABLE users IS 'Utilisateurs admin pour interface web';
COMMENT ON TABLE conversations IS 'Historique des conversations chat';
COMMENT ON TABLE messages IS 'Messages individuels dans conversations';
COMMENT ON TABLE message_ratings IS 'Notations thumbs up/down des réponses';
COMMENT ON TABLE ingestion_jobs IS 'Suivi des jobs d ingestion de documents';
COMMENT ON VIEW conversation_stats IS 'Statistiques agrégées par conversation';
COMMENT ON VIEW document_stats IS 'Statistiques agrégées par document';

-- ============================================================================
-- RÉCAPITULATIF
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE '✅ Base de données RAGFab initialisée avec succès !';
    RAISE NOTICE '';
    RAISE NOTICE '📚 Schéma RAG : documents + chunks (1024D vectors)';
    RAISE NOTICE '💬 Schéma Web : users + conversations + messages + ratings + jobs';
    RAISE NOTICE '';
    RAISE NOTICE '👤 Admin par défaut : admin / admin';
    RAISE NOTICE '⚠️  CHANGEZ CE MOT DE PASSE EN PRODUCTION !';
END $$;
