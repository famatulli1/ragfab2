-- ============================================================================
-- RAGFab - Script d'initialisation complet PostgreSQL
-- Exécuté automatiquement au premier démarrage du container
-- ============================================================================

-- Extensions nécessaires
CREATE EXTENSION IF NOT EXISTS vector;
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- ============================================================================
-- SCHEMA RAG (Documents et Chunks)
-- ============================================================================

-- Table des documents
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    title VARCHAR(500) NOT NULL,
    source VARCHAR(500),
    content_type VARCHAR(100),
    file_size BIGINT,
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_documents_created_at ON documents(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_documents_metadata ON documents USING gin(metadata);

-- Table des chunks (morceaux de texte vectorisés)
CREATE TABLE IF NOT EXISTS chunks (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    document_id UUID NOT NULL REFERENCES documents(id) ON DELETE CASCADE,
    chunk_index INTEGER NOT NULL,
    content TEXT NOT NULL,
    token_count INTEGER,
    embedding vector(1024), -- multilingual-e5-large dimensions
    metadata JSONB DEFAULT '{}'::jsonb,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(document_id, chunk_index)
);

CREATE INDEX IF NOT EXISTS idx_chunks_document_id ON chunks(document_id);
CREATE INDEX IF NOT EXISTS idx_chunks_chunk_index ON chunks(chunk_index);
-- Index HNSW pour recherche vectorielle rapide (créé après insertion de données)
CREATE INDEX IF NOT EXISTS idx_chunks_embedding ON chunks USING hnsw (embedding vector_cosine_ops);

-- Fonction de recherche vectorielle
CREATE OR REPLACE FUNCTION match_chunks(
    query_embedding vector(1024),
    match_count integer DEFAULT 5,
    similarity_threshold float DEFAULT 0.5
)
RETURNS TABLE (
    id uuid,
    document_id uuid,
    content text,
    similarity float
)
LANGUAGE plpgsql
AS $$
BEGIN
    RETURN QUERY
    SELECT
        c.id,
        c.document_id,
        c.content,
        1 - (c.embedding <=> query_embedding) as similarity
    FROM chunks c
    WHERE 1 - (c.embedding <=> query_embedding) > similarity_threshold
    ORDER BY c.embedding <=> query_embedding
    LIMIT match_count;
END;
$$;

-- Trigger pour mettre à jour le timestamp
CREATE OR REPLACE FUNCTION update_document_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    UPDATE documents
    SET created_at = CURRENT_TIMESTAMP
    WHERE id = NEW.document_id;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER update_doc_on_chunk_insert
    AFTER INSERT ON chunks
    FOR EACH ROW
    EXECUTE FUNCTION update_document_timestamp();

-- ============================================================================
-- SCHEMA WEB (Authentification, Conversations, Messages)
-- ============================================================================

-- Table des utilisateurs admin
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    username VARCHAR(100) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    is_active BOOLEAN DEFAULT true,
    is_admin BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);
CREATE INDEX IF NOT EXISTS idx_users_email ON users(email);

-- Table des conversations
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255),
    provider VARCHAR(50) DEFAULT 'mistral',
    use_tools BOOLEAN DEFAULT true,
    archived BOOLEAN DEFAULT false,
    message_count INTEGER DEFAULT 0,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);
CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON conversations(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversations_updated_at ON conversations(updated_at DESC);

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
    is_regenerated BOOLEAN DEFAULT false,
    parent_message_id UUID REFERENCES messages(id) ON DELETE SET NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);
CREATE INDEX IF NOT EXISTS idx_messages_role ON messages(role);

-- Table des notations
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

-- Fonction pour mettre à jour updated_at automatiquement
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

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
    c.archived,
    c.message_count,
    COALESCE(MAX(m.created_at), c.created_at) AS last_message_at
FROM conversations c
LEFT JOIN messages m ON c.id = m.conversation_id
GROUP BY c.id, c.title, c.provider, c.use_tools, c.created_at, c.updated_at, c.archived, c.message_count;

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

-- Créer utilisateur admin par défaut
-- Username: admin
-- Password: admin
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

COMMENT ON TABLE documents IS 'Documents ingérés dans le système RAG';
COMMENT ON TABLE chunks IS 'Chunks vectorisés des documents';
COMMENT ON TABLE users IS 'Utilisateurs admin pour l''interface web';
COMMENT ON TABLE conversations IS 'Historique des conversations chat';
COMMENT ON TABLE messages IS 'Messages individuels dans les conversations';
COMMENT ON TABLE message_ratings IS 'Notations (thumbs up/down) des réponses';
COMMENT ON TABLE ingestion_jobs IS 'Suivi des jobs d''ingestion de documents';
COMMENT ON VIEW conversation_stats IS 'Statistiques agrégées par conversation';
COMMENT ON VIEW document_stats IS 'Statistiques agrégées par document';

-- ============================================================================
-- RÉCAPITULATIF
-- ============================================================================

DO $$
BEGIN
    RAISE NOTICE '✅ Base de données RAGFab initialisée avec succès !';
    RAISE NOTICE '';
    RAISE NOTICE '📚 Schéma RAG :';
    RAISE NOTICE '  - documents (stockage des documents)';
    RAISE NOTICE '  - chunks (morceaux vectorisés, 1024 dimensions)';
    RAISE NOTICE '';
    RAISE NOTICE '💬 Schéma Web :';
    RAISE NOTICE '  - users (authentification admin)';
    RAISE NOTICE '  - conversations (historique chat)';
    RAISE NOTICE '  - messages (messages individuels)';
    RAISE NOTICE '  - message_ratings (notations thumbs up/down)';
    RAISE NOTICE '  - ingestion_jobs (suivi uploads)';
    RAISE NOTICE '';
    RAISE NOTICE '👤 Utilisateur admin par défaut :';
    RAISE NOTICE '  - Username: admin';
    RAISE NOTICE '  - Password: admin';
    RAISE NOTICE '  ⚠️  CHANGEZ CE MOT DE PASSE EN PRODUCTION !';
END $$;
