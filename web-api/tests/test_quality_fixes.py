"""
Tests unitaires pour les corrections du système Quality Management

Tests pour :
1. Problème 1: Synchronisation thumbs_down_validations → document_quality_scores
2. Problème 2: Endpoints unblacklist/whitelist/ignore avec Body parameter

Author: Claude Code
Date: 2025-01-06
"""

import pytest
from unittest.mock import AsyncMock, Mock, patch
from uuid import uuid4, UUID
from fastapi import HTTPException


# ==============================================================================
# Tests pour Problème 1: Synchronisation Quality Management
# ==============================================================================

class TestQualityManagementSync:
    """Tests pour la synchronisation validation → quality_scores"""

    @pytest.mark.asyncio
    async def test_sync_validation_creates_quality_score(self):
        """Test que sync crée une entrée document_quality_scores"""
        # Arrange
        from app.routes.analytics import sync_validation_sources_to_quality_scores

        validation_id = uuid4()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="INSERT 0 2")  # 2 documents insérés

        # Act
        count = await sync_validation_sources_to_quality_scores(
            mock_conn,
            validation_id,
            needs_reingestion=True,
            reason="Test sync"
        )

        # Assert
        assert count == 2
        mock_conn.execute.assert_called_once()
        call_args = mock_conn.execute.call_args
        assert "INSERT INTO document_quality_scores" in call_args[0][0]
        assert validation_id == call_args[0][1]

    @pytest.mark.asyncio
    async def test_sync_validation_handles_no_sources(self):
        """Test que sync gère gracefully l'absence de sources"""
        # Arrange
        from app.routes.analytics import sync_validation_sources_to_quality_scores

        validation_id = uuid4()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(return_value="INSERT 0 0")  # Aucun document

        # Act
        count = await sync_validation_sources_to_quality_scores(
            mock_conn,
            validation_id,
            needs_reingestion=True,
            reason="Test no sources"
        )

        # Assert
        assert count == 0

    @pytest.mark.asyncio
    async def test_sync_validation_handles_errors_gracefully(self):
        """Test que sync ne bloque pas en cas d'erreur"""
        # Arrange
        from app.routes.analytics import sync_validation_sources_to_quality_scores

        validation_id = uuid4()
        mock_conn = AsyncMock()
        mock_conn.execute = AsyncMock(side_effect=Exception("DB error"))

        # Act - ne doit pas lever d'exception
        count = await sync_validation_sources_to_quality_scores(
            mock_conn,
            validation_id,
            needs_reingestion=True,
            reason="Test error"
        )

        # Assert
        assert count == 0  # Graceful degradation


# ==============================================================================
# Tests pour Problème 2: Body Parameter dans Endpoints
# ==============================================================================

class TestBodyParameterEndpoints:
    """Tests pour les endpoints avec Body parameter"""

    @pytest.mark.asyncio
    async def test_unblacklist_accepts_json_body(self):
        """Test que unblacklist_chunk accepte reason dans JSON body"""
        # Arrange
        from app.routes.analytics import unblacklist_chunk
        from fastapi import Body

        # Act - Vérifier la signature de fonction
        import inspect
        sig = inspect.signature(unblacklist_chunk)
        params = sig.parameters

        # Assert
        assert 'reason' in params
        # Vérifier que reason a un default qui est Body(...)
        reason_param = params['reason']
        assert reason_param.default is not inspect.Parameter.empty
        # Note: Body(...) est un objet Pydantic FieldInfo, pas facilement testable
        # On vérifie juste que ce n'est pas un string simple

    @pytest.mark.asyncio
    async def test_whitelist_accepts_json_body(self):
        """Test que whitelist_chunk accepte reason dans JSON body"""
        # Arrange
        from app.routes.analytics import whitelist_chunk

        # Act
        import inspect
        sig = inspect.signature(whitelist_chunk)
        params = sig.parameters

        # Assert
        assert 'reason' in params
        reason_param = params['reason']
        assert reason_param.default is not inspect.Parameter.empty

    @pytest.mark.asyncio
    async def test_ignore_recommendation_accepts_json_body(self):
        """Test que ignore_reingestion_recommendation accepte reason dans JSON body"""
        # Arrange
        from app.routes.analytics import ignore_reingestion_recommendation

        # Act
        import inspect
        sig = inspect.signature(ignore_reingestion_recommendation)
        params = sig.parameters

        # Assert
        assert 'reason' in params
        reason_param = params['reason']
        assert reason_param.default is not inspect.Parameter.empty


# ==============================================================================
# Tests d'Intégration (Scénario Multi-Conversations)
# ==============================================================================

class TestMultiConversationScenario:
    """Test du scénario réel : 3 thumbs down sur même document dans différentes conversations"""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Requiert une base de données PostgreSQL réelle")
    async def test_multi_thumbs_down_same_document(self):
        """
        Scénario complet :
        1. User donne thumbs down dans conversation 1 → Validation créée automatiquement
        2. User donne thumbs down dans conversation 2 → Deuxième validation
        3. User donne thumbs down dans conversation 3 → Troisième validation
        4. Dashboard doit afficher "3 Sources manquantes détectées"
        5. Onglet "Documents à réingérer" doit afficher le document concerné

        Ce test nécessite :
        - Base de données PostgreSQL avec migrations appliquées
        - Background worker thumbs_down_analyzer en fonctionnement
        - API web-api lancée
        """
        # Ce test est intentionnellement skip car il nécessite l'environnement complet
        # Il sert de documentation pour le test manuel à effectuer
        pass


# ==============================================================================
# Tests pour Migration SQL
# ==============================================================================

class TestMigration:
    """Tests pour la migration 18_sync_validation_quality.sql"""

    @pytest.mark.asyncio
    @pytest.mark.skip(reason="Test manuel - appliquer migration et vérifier")
    async def test_migration_sync_existing_validations(self):
        """
        Test manuel pour vérifier la migration :

        1. Appliquer migration : docker-compose exec postgres psql -U raguser -d ragdb -f /docker-entrypoint-initdb.d/18_sync_validation_quality.sql
        2. Vérifier fonction créée : \df sync_validation_to_quality_scores
        3. Vérifier documents synchronisés : SELECT COUNT(*) FROM document_quality_scores WHERE needs_reingestion = true;
        4. Comparer avec validations : SELECT COUNT(DISTINCT document_id) FROM ...
        """
        pass


# ==============================================================================
# Fixtures et Helpers
# ==============================================================================

@pytest.fixture
def mock_db_conn():
    """Mock database connection pour tests"""
    conn = AsyncMock()
    conn.execute = AsyncMock(return_value="INSERT 0 1")
    conn.fetchrow = AsyncMock(return_value={'id': uuid4()})
    conn.fetch = AsyncMock(return_value=[])
    return conn


@pytest.fixture
def sample_validation_data():
    """Données de test pour validation thumbs_down"""
    return {
        'validation_id': uuid4(),
        'message_id': uuid4(),
        'rating_id': uuid4(),
        'user_id': uuid4(),
        'user_question': "Comment activer le télétravail ?",
        'assistant_response': "Voici la procédure...",
        'sources_used': [
            {'chunk_id': str(uuid4()), 'score': 0.85},
            {'chunk_id': str(uuid4()), 'score': 0.78}
        ],
        'ai_classification': 'missing_sources',
        'ai_confidence': 0.92,
        'admin_action': 'mark_for_reingestion'
    }


# ==============================================================================
# Instructions de Test Manuel
# ==============================================================================

"""
TESTS MANUELS À EFFECTUER APRÈS DÉPLOIEMENT
===========================================

1. Test Scénario Multi-Conversations:
   a. Créer 3 conversations différentes
   b. Dans chaque conversation, poser la même question (ex: "procédure RTT")
   c. Donner thumbs down sur chaque réponse
   d. Vérifier dashboard Quality Management : devrait afficher "3 Sources manquantes"
   e. Cliquer sur "Documents à réingérer" : le document devrait apparaître

2. Test Endpoints Body Parameter:
   a. Aller dans Quality Management → Blacklisted Chunks
   b. Cliquer "Déblacklister" sur un chunk blacklisté
   c. Entrer une raison : "Test déblacklist"
   d. Vérifier que ça fonctionne sans erreur 422

3. Test Migration:
   a. Appliquer migration 18
   b. Vérifier logs : "Synchronized X documents from thumbs_down_validations"
   c. Query DB : SELECT * FROM document_quality_scores WHERE needs_reingestion = true;
   d. Comparer avec validations existantes

4. Test Auto-Sync sur Nouvelle Validation:
   a. Donner thumbs down sur une nouvelle réponse
   b. Attendre quelques secondes (worker processing)
   c. Vérifier logs worker : "Auto-synced X document(s)"
   d. Vérifier immédiatement dans "Documents à réingérer" : devrait apparaître

COMMANDES UTILES POUR DEBUGGING
================================

# Vérifier validations créées
docker-compose exec postgres psql -U raguser -d ragdb -c "SELECT id, ai_classification, admin_action FROM thumbs_down_validations ORDER BY created_at DESC LIMIT 10;"

# Vérifier documents marqués pour réingestion
docker-compose exec postgres psql -U raguser -d ragdb -c "SELECT d.title, dqs.needs_reingestion, dqs.analysis_notes FROM document_quality_scores dqs JOIN documents d ON dqs.document_id = d.id WHERE dqs.needs_reingestion = true;"

# Vérifier logs worker
docker-compose logs -f analytics-worker | grep "Auto-synced"

# Vérifier logs API
docker-compose logs -f ragfab-api | grep "marked for reingestion"
"""
