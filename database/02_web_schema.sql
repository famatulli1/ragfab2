-- ============================================================================
-- RAGFab Web Interface Schema
-- Tables pour authentification, conversations, messages et ratings
-- ============================================================================

-- Table des utilisateurs admin
CREATE TABLE IF NOT EXISTS users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(255) UNIQUE NOT NULL,
    hashed_password TEXT NOT NULL,
    email VARCHAR(255),
    is_active BOOLEAN DEFAULT true,
    is_admin BOOLEAN DEFAULT true,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    last_login TIMESTAMP WITH TIME ZONE
);

-- Index pour recherche rapide par username
CREATE INDEX IF NOT EXISTS idx_users_username ON users(username);

-- Table des conversations
CREATE TABLE IF NOT EXISTS conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID NOT NULL REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(500) DEFAULT 'Nouvelle conversation',
    provider VARCHAR(50) NOT NULL DEFAULT 'mistral', -- mistral, chocolatine
    use_tools BOOLEAN DEFAULT true,
    reranking_enabled BOOLEAN DEFAULT false,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    message_count INTEGER DEFAULT 0,
    archived BOOLEAN DEFAULT false
);

-- Index pour tri par date
CREATE INDEX IF NOT EXISTS idx_conversations_created_at ON conversations(created_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversations_updated_at ON conversations(updated_at DESC);
CREATE INDEX IF NOT EXISTS idx_conversations_user_id ON conversations(user_id);

-- Table des messages
CREATE TABLE IF NOT EXISTS messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL, -- 'user' ou 'assistant'
    content TEXT NOT NULL,
    sources JSONB, -- Liste des sources utilisées pour la réponse
    provider VARCHAR(50), -- Provider utilisé pour ce message (mistral, chocolatine)
    model_name VARCHAR(100), -- Nom du modèle utilisé
    token_usage JSONB, -- Informations sur les tokens utilisés
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    is_regenerated BOOLEAN DEFAULT false,
    parent_message_id UUID REFERENCES messages(id) ON DELETE SET NULL -- Pour les régénérations
);

-- Index pour récupération rapide des messages d'une conversation
CREATE INDEX IF NOT EXISTS idx_messages_conversation_id ON messages(conversation_id);
CREATE INDEX IF NOT EXISTS idx_messages_created_at ON messages(created_at);
CREATE INDEX IF NOT EXISTS idx_messages_role ON messages(role);

-- Table des notations de messages (thumbs up/down)
CREATE TABLE IF NOT EXISTS message_ratings (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    message_id UUID NOT NULL REFERENCES messages(id) ON DELETE CASCADE,
    rating SMALLINT NOT NULL CHECK (rating IN (-1, 1)), -- -1 = thumbs down, 1 = thumbs up
    feedback TEXT, -- Commentaire optionnel
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(message_id) -- Un seul rating par message
);

-- Index pour analytics
CREATE INDEX IF NOT EXISTS idx_message_ratings_message_id ON message_ratings(message_id);
CREATE INDEX IF NOT EXISTS idx_message_ratings_rating ON message_ratings(rating);

-- Table des jobs d'ingestion (pour suivi de progression)
CREATE TABLE IF NOT EXISTS ingestion_jobs (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    filename VARCHAR(500) NOT NULL,
    file_size BIGINT, -- Taille en bytes
    status VARCHAR(50) NOT NULL DEFAULT 'pending', -- pending, processing, completed, failed
    progress INTEGER DEFAULT 0, -- 0-100%
    document_id UUID REFERENCES documents(id) ON DELETE SET NULL,
    chunks_created INTEGER DEFAULT 0,
    error_message TEXT,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    started_at TIMESTAMP WITH TIME ZONE,
    completed_at TIMESTAMP WITH TIME ZONE
);

-- Index pour suivi des jobs
CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_status ON ingestion_jobs(status);
CREATE INDEX IF NOT EXISTS idx_ingestion_jobs_created_at ON ingestion_jobs(created_at DESC);

-- Fonction pour mettre à jour le timestamp updated_at automatiquement
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

-- Trigger pour mettre à jour conversations.updated_at
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

-- Trigger pour incrémenter le compteur lors de l'ajout d'un message
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

-- Trigger pour décrémenter le compteur lors de la suppression d'un message
DROP TRIGGER IF EXISTS decrement_conversation_message_count ON messages;
CREATE TRIGGER decrement_conversation_message_count
    AFTER DELETE ON messages
    FOR EACH ROW
    EXECUTE FUNCTION decrement_message_count();

-- Vue pour statistiques des conversations
CREATE OR REPLACE VIEW conversation_stats AS
SELECT
    c.id,
    c.user_id,
    c.title,
    c.provider,
    c.use_tools,
    c.reranking_enabled,
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
GROUP BY c.id, c.user_id, c.title, c.provider, c.use_tools, c.reranking_enabled, c.created_at, c.updated_at, c.message_count, c.archived;

-- Vue pour statistiques des documents (réutilise la table existante)
CREATE OR REPLACE VIEW document_stats AS
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

-- Commentaires pour documentation
COMMENT ON TABLE users IS 'Utilisateurs admin pour l''interface web';
COMMENT ON TABLE conversations IS 'Historique des conversations chat';
COMMENT ON TABLE messages IS 'Messages individuels dans les conversations';
COMMENT ON TABLE message_ratings IS 'Notations (thumbs up/down) des réponses';
COMMENT ON TABLE ingestion_jobs IS 'Suivi des jobs d''ingestion de documents';
COMMENT ON VIEW conversation_stats IS 'Statistiques agrégées par conversation';
COMMENT ON VIEW document_stats IS 'Statistiques agrégées par document';

-- Seed data : Créer un utilisateur admin par défaut
-- Mot de passe: 'admin' (hash bcrypt)
INSERT INTO users (username, hashed_password, email, is_admin)
VALUES (
    'admin',
    '$2b$12$1bs.lMmsO5iuv3.fP7oU3eNCspUfHUPeyOKUXx3mZKTdLu/vsYurq', -- 'admin'
    'admin@ragfab.local',
    true
)
ON CONFLICT (username) DO NOTHING;

-- Afficher le récapitulatif
DO $$
BEGIN
    RAISE NOTICE '✅ Schéma web créé avec succès !';
    RAISE NOTICE '';
    RAISE NOTICE 'Tables créées :';
    RAISE NOTICE '  - users (authentification admin)';
    RAISE NOTICE '  - conversations (historique chat)';
    RAISE NOTICE '  - messages (messages individuels)';
    RAISE NOTICE '  - message_ratings (notations thumbs up/down)';
    RAISE NOTICE '  - ingestion_jobs (suivi uploads)';
    RAISE NOTICE '';
    RAISE NOTICE 'Vues créées :';
    RAISE NOTICE '  - conversation_stats';
    RAISE NOTICE '  - document_stats';
    RAISE NOTICE '';
    RAISE NOTICE 'Utilisateur admin par défaut :';
    RAISE NOTICE '  - Username: admin';
    RAISE NOTICE '  - Password: admin';
    RAISE NOTICE '  ⚠️  CHANGEZ CE MOT DE PASSE EN PRODUCTION !';
END $$;
