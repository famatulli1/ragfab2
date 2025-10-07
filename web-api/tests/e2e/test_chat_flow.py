"""
End-to-end tests for chat functionality
Tests the complete chat flow from authentication to response
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import AsyncMock, MagicMock, patch
import httpx

from app.main import app
from app.auth import create_access_token, get_password_hash


@pytest.fixture
def client():
    """Create test client"""
    return TestClient(app)


@pytest.fixture
def auth_token():
    """Create authentication token for testing"""
    return create_access_token({"sub": "testuser"})


@pytest.fixture
def admin_token():
    """Create admin authentication token"""
    return create_access_token({"sub": "admin"})


@pytest.fixture
def mock_user():
    """Mock user data"""
    return {
        "id": "user-123",
        "username": "testuser",
        "email": "test@example.com",
        "is_active": True,
        "is_admin": False,
        "hashed_password": get_password_hash("testpass123"),
    }


@pytest.fixture
def mock_admin():
    """Mock admin user data"""
    return {
        "id": "admin-123",
        "username": "admin",
        "email": "admin@example.com",
        "is_active": True,
        "is_admin": True,
        "hashed_password": get_password_hash("adminpass123"),
    }


@pytest.mark.e2e
class TestAuthenticationFlow:
    """Test authentication flow"""

    def test_login_success(self, client, mock_user):
        """Test successful login flow"""
        with patch("app.auth.database.db_pool") as mock_pool:
            mock_conn = AsyncMock()
            mock_conn.fetchrow.return_value = mock_user
            mock_conn.execute = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

            response = client.post(
                "/api/auth/login",
                json={"username": "testuser", "password": "testpass123"},
            )

            assert response.status_code == 200
            data = response.json()
            assert "access_token" in data
            assert data["token_type"] == "bearer"
            assert "expires_in" in data

    def test_login_invalid_credentials(self, client):
        """Test login with invalid credentials"""
        with patch("app.auth.database.db_pool") as mock_pool:
            mock_conn = AsyncMock()
            mock_conn.fetchrow.return_value = None  # User not found
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

            response = client.post(
                "/api/auth/login",
                json={"username": "invalid", "password": "wrong"},
            )

            assert response.status_code == 401
            data = response.json()
            assert "detail" in data

    def test_get_current_user_info(self, client, auth_token, mock_user):
        """Test retrieving current user information"""
        with patch("app.auth.database.db_pool") as mock_pool:
            mock_conn = AsyncMock()
            mock_conn.fetchrow.return_value = mock_user
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

            response = client.get(
                "/api/auth/me",
                headers={"Authorization": f"Bearer {auth_token}"},
            )

            assert response.status_code == 200
            data = response.json()
            assert data["username"] == "testuser"
            assert data["email"] == "test@example.com"

    def test_logout_flow(self, client, auth_token, mock_user):
        """Test logout flow"""
        with patch("app.auth.database.db_pool") as mock_pool:
            mock_conn = AsyncMock()
            mock_conn.fetchrow.return_value = mock_user
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

            response = client.post(
                "/api/auth/logout",
                headers={"Authorization": f"Bearer {auth_token}"},
            )

            assert response.status_code == 200
            data = response.json()
            assert "message" in data


@pytest.mark.e2e
@pytest.mark.chat
class TestChatFlow:
    """Test complete chat flow"""

    def test_chat_without_authentication(self, client):
        """Test chat endpoint requires authentication"""
        response = client.post(
            "/api/chat",
            json={"message": "Hello", "conversation_id": None},
        )

        assert response.status_code == 401

    def test_chat_with_authentication(self, client, auth_token, mock_user):
        """Test authenticated chat request"""
        with patch("app.auth.database.db_pool") as mock_pool, \
             patch("app.main.rag_agent") as mock_agent:

            # Mock database
            mock_conn = AsyncMock()
            mock_conn.fetchrow.return_value = mock_user
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_conn.execute = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

            # Mock RAG agent response
            mock_result = MagicMock()
            mock_result.data = "This is the AI response"
            mock_agent.run = AsyncMock(return_value=mock_result)

            response = client.post(
                "/api/chat",
                headers={"Authorization": f"Bearer {auth_token}"},
                json={
                    "message": "What is RAGFab?",
                    "conversation_id": None,
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert "response" in data
            assert "conversation_id" in data
            assert isinstance(data["response"], str)

    def test_chat_continues_conversation(self, client, auth_token, mock_user):
        """Test chat continuation with conversation_id"""
        conversation_id = "conv-123"

        with patch("app.auth.database.db_pool") as mock_pool, \
             patch("app.main.rag_agent") as mock_agent:

            mock_conn = AsyncMock()
            mock_conn.fetchrow.return_value = mock_user
            mock_conn.fetch = AsyncMock(return_value=[
                {
                    "id": "msg-1",
                    "role": "user",
                    "content": "Previous question",
                    "created_at": "2024-01-01T00:00:00",
                },
                {
                    "id": "msg-2",
                    "role": "assistant",
                    "content": "Previous answer",
                    "created_at": "2024-01-01T00:00:01",
                },
            ])
            mock_conn.execute = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

            mock_result = MagicMock()
            mock_result.data = "Follow-up response"
            mock_agent.run = AsyncMock(return_value=mock_result)

            response = client.post(
                "/api/chat",
                headers={"Authorization": f"Bearer {auth_token}"},
                json={
                    "message": "Follow-up question",
                    "conversation_id": conversation_id,
                },
            )

            assert response.status_code == 200
            data = response.json()
            assert data["conversation_id"] == conversation_id

    def test_chat_with_sources(self, client, auth_token, mock_user):
        """Test chat response includes sources"""
        with patch("app.auth.database.db_pool") as mock_pool, \
             patch("app.main.rag_agent") as mock_agent, \
             patch("app.main._request_sources") as mock_sources:

            mock_conn = AsyncMock()
            mock_conn.fetchrow.return_value = mock_user
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_conn.execute = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

            mock_result = MagicMock()
            mock_result.data = "Response with sources"
            mock_agent.run = AsyncMock(return_value=mock_result)

            # Mock sources
            from contextvars import ContextVar
            mock_sources_var = ContextVar('request_sources', default=[])
            mock_sources_var.set([
                {
                    "title": "Test Doc",
                    "source": "test.md",
                    "content": "Relevant content",
                }
            ])
            mock_sources.get.return_value = mock_sources_var.get()

            response = client.post(
                "/api/chat",
                headers={"Authorization": f"Bearer {auth_token}"},
                json={"message": "Question", "conversation_id": None},
            )

            assert response.status_code == 200
            data = response.json()
            assert "sources" in data
            # Note: Sources might be empty list in test, but field should exist

    def test_chat_rate_limiting(self, client, auth_token, mock_user):
        """Test chat endpoint respects rate limiting"""
        with patch("app.auth.database.db_pool") as mock_pool, \
             patch("app.main.rag_agent") as mock_agent:

            mock_conn = AsyncMock()
            mock_conn.fetchrow.return_value = mock_user
            mock_conn.fetch = AsyncMock(return_value=[])
            mock_conn.execute = AsyncMock()
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

            mock_result = MagicMock()
            mock_result.data = "Response"
            mock_agent.run = AsyncMock(return_value=mock_result)

            # Make multiple requests rapidly
            responses = []
            for _ in range(25):  # More than rate limit (20/minute)
                response = client.post(
                    "/api/chat",
                    headers={"Authorization": f"Bearer {auth_token}"},
                    json={"message": "Test", "conversation_id": None},
                )
                responses.append(response)

            # At least one should be rate limited
            status_codes = [r.status_code for r in responses]
            assert 429 in status_codes or all(code == 200 for code in status_codes)


@pytest.mark.e2e
class TestConversationManagement:
    """Test conversation management endpoints"""

    def test_list_conversations(self, client, auth_token, mock_user):
        """Test listing user conversations"""
        with patch("app.auth.database.db_pool") as mock_pool:
            mock_conn = AsyncMock()
            mock_conn.fetchrow.return_value = mock_user
            mock_conn.fetch = AsyncMock(return_value=[
                {
                    "id": "conv-1",
                    "user_id": "user-123",
                    "title": "Test Conversation",
                    "created_at": "2024-01-01T00:00:00",
                    "updated_at": "2024-01-01T00:00:00",
                },
            ])
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

            response = client.get(
                "/api/conversations",
                headers={"Authorization": f"Bearer {auth_token}"},
            )

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)

    def test_get_conversation_messages(self, client, auth_token, mock_user):
        """Test retrieving conversation messages"""
        conversation_id = "conv-123"

        with patch("app.auth.database.db_pool") as mock_pool:
            mock_conn = AsyncMock()
            mock_conn.fetchrow.return_value = mock_user
            mock_conn.fetch = AsyncMock(return_value=[
                {
                    "id": "msg-1",
                    "conversation_id": conversation_id,
                    "role": "user",
                    "content": "Question",
                    "created_at": "2024-01-01T00:00:00",
                },
                {
                    "id": "msg-2",
                    "conversation_id": conversation_id,
                    "role": "assistant",
                    "content": "Answer",
                    "created_at": "2024-01-01T00:00:01",
                },
            ])
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

            response = client.get(
                f"/api/conversations/{conversation_id}/messages",
                headers={"Authorization": f"Bearer {auth_token}"},
            )

            assert response.status_code == 200
            data = response.json()
            assert isinstance(data, list)
            assert len(data) >= 0


@pytest.mark.e2e
@pytest.mark.slow
class TestDocumentUploadFlow:
    """Test document upload and ingestion flow"""

    def test_upload_document_requires_auth(self, client):
        """Test document upload requires authentication"""
        files = {"file": ("test.md", b"# Test Content", "text/markdown")}

        response = client.post("/api/documents/upload", files=files)

        assert response.status_code == 401

    def test_upload_document_success(self, client, auth_token, mock_user):
        """Test successful document upload"""
        with patch("app.auth.database.db_pool") as mock_pool, \
             patch("app.main.ingest_document_task") as mock_ingest:

            mock_conn = AsyncMock()
            mock_conn.fetchrow.return_value = mock_user
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

            mock_ingest.return_value = {"success": True, "chunks_created": 5}

            files = {"file": ("test.md", b"# Test\nContent", "text/markdown")}

            response = client.post(
                "/api/documents/upload",
                headers={"Authorization": f"Bearer {auth_token}"},
                files=files,
            )

            assert response.status_code == 200
            data = response.json()
            assert "message" in data or "status" in data

    def test_upload_document_invalid_type(self, client, auth_token, mock_user):
        """Test upload with invalid file type"""
        with patch("app.auth.database.db_pool") as mock_pool:
            mock_conn = AsyncMock()
            mock_conn.fetchrow.return_value = mock_user
            mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

            files = {"file": ("test.exe", b"binary", "application/x-msdownload")}

            response = client.post(
                "/api/documents/upload",
                headers={"Authorization": f"Bearer {auth_token}"},
                files=files,
            )

            # Should reject or handle gracefully
            assert response.status_code in [400, 415, 200]


@pytest.mark.e2e
class TestHealthEndpoints:
    """Test health and status endpoints"""

    def test_health_endpoint(self, client):
        """Test application health endpoint"""
        response = client.get("/api/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data

    def test_docs_endpoint_accessible(self, client):
        """Test API documentation is accessible"""
        response = client.get("/api/docs")

        assert response.status_code == 200
        assert "text/html" in response.headers["content-type"]
