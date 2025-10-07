"""
Shared pytest fixtures for web-api tests
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock

from app.main import app
from app.auth import get_password_hash, create_access_token


@pytest.fixture(scope="session")
def test_app():
    """Create test application instance"""
    return app


@pytest.fixture
def client(test_app):
    """Create test client"""
    return TestClient(test_app)


@pytest.fixture
def mock_db_pool():
    """Create mock database pool"""
    pool = MagicMock()
    conn = AsyncMock()
    pool.acquire.return_value.__aenter__.return_value = conn
    return pool


@pytest.fixture
def mock_db_conn():
    """Create mock database connection"""
    conn = AsyncMock()
    conn.execute = AsyncMock()
    conn.fetch = AsyncMock(return_value=[])
    conn.fetchrow = AsyncMock(return_value=None)
    return conn


@pytest.fixture
def sample_user():
    """Sample user data for testing"""
    return {
        "id": "user-123",
        "username": "testuser",
        "email": "test@example.com",
        "is_active": True,
        "is_admin": False,
        "hashed_password": get_password_hash("testpass123"),
        "created_at": "2024-01-01T00:00:00",
        "last_login": None,
    }


@pytest.fixture
def sample_admin():
    """Sample admin user for testing"""
    return {
        "id": "admin-123",
        "username": "admin",
        "email": "admin@example.com",
        "is_active": True,
        "is_admin": True,
        "hashed_password": get_password_hash("adminpass123"),
        "created_at": "2024-01-01T00:00:00",
        "last_login": None,
    }


@pytest.fixture
def auth_token(sample_user):
    """Create authentication token for testing"""
    return create_access_token({"sub": sample_user["username"]})


@pytest.fixture
def admin_token(sample_admin):
    """Create admin authentication token"""
    return create_access_token({"sub": sample_admin["username"]})


@pytest.fixture
def auth_headers(auth_token):
    """Create authentication headers"""
    return {"Authorization": f"Bearer {auth_token}"}


@pytest.fixture
def admin_headers(admin_token):
    """Create admin authentication headers"""
    return {"Authorization": f"Bearer {admin_token}"}
