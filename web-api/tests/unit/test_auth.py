"""
Unit tests for app/auth.py
Tests authentication, JWT token generation, and password hashing
"""

import pytest
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch
from jose import jwt, JWTError
from fastapi import HTTPException, status

from app.auth import (
    verify_password,
    get_password_hash,
    create_access_token,
    decode_access_token,
    authenticate_user,
    get_current_user,
    get_current_admin_user,
    pwd_context,
    security,
)
from app.config import settings


@pytest.fixture
def mock_db_pool():
    """Create mock database pool"""
    pool = MagicMock()
    conn = MagicMock()
    pool.acquire.return_value.__aenter__.return_value = conn
    return pool, conn


@pytest.fixture
def sample_user():
    """Sample user data"""
    return {
        "id": "user-123",
        "username": "testuser",
        "hashed_password": get_password_hash("testpassword"),
        "is_active": True,
        "is_admin": False,
        "email": "test@example.com",
        "created_at": datetime.now(),
        "last_login": None,
    }


@pytest.fixture
def sample_admin():
    """Sample admin user data"""
    return {
        "id": "admin-123",
        "username": "admin",
        "hashed_password": get_password_hash("adminpassword"),
        "is_active": True,
        "is_admin": True,
        "email": "admin@example.com",
        "created_at": datetime.now(),
        "last_login": None,
    }


@pytest.mark.unit
class TestPasswordHashing:
    """Test password hashing and verification"""

    def test_hash_password(self):
        """Test password hashing"""
        password = "test_password_123"
        hashed = get_password_hash(password)

        assert hashed != password
        assert hashed.startswith("$2b$")  # bcrypt format
        assert len(hashed) == 60  # bcrypt hash length

    def test_verify_password_correct(self):
        """Test password verification with correct password"""
        password = "correct_password"
        hashed = get_password_hash(password)

        assert verify_password(password, hashed) is True

    def test_verify_password_incorrect(self):
        """Test password verification with incorrect password"""
        password = "correct_password"
        wrong_password = "wrong_password"
        hashed = get_password_hash(password)

        assert verify_password(wrong_password, hashed) is False

    def test_hash_different_passwords_different_hashes(self):
        """Test that same password produces different hashes (salt)"""
        password = "same_password"
        hash1 = get_password_hash(password)
        hash2 = get_password_hash(password)

        assert hash1 != hash2  # Different salts
        assert verify_password(password, hash1)
        assert verify_password(password, hash2)

    def test_password_context_uses_bcrypt(self):
        """Test that password context is configured to use bcrypt"""
        assert "bcrypt" in pwd_context.schemes()


@pytest.mark.unit
class TestJWTTokens:
    """Test JWT token creation and decoding"""

    def test_create_access_token(self):
        """Test JWT token creation"""
        data = {"sub": "testuser"}
        token = create_access_token(data)

        assert isinstance(token, str)
        assert len(token) > 0

        # Verify token can be decoded
        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )
        assert payload["sub"] == "testuser"
        assert "exp" in payload

    def test_create_access_token_with_expiration(self):
        """Test token creation with custom expiration"""
        data = {"sub": "testuser"}
        expires_delta = timedelta(minutes=30)
        token = create_access_token(data, expires_delta)

        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )

        # Verify expiration is approximately 30 minutes from now
        exp_time = datetime.fromtimestamp(payload["exp"])
        expected_exp = datetime.utcnow() + expires_delta
        time_diff = abs((exp_time - expected_exp).total_seconds())
        assert time_diff < 5  # Within 5 seconds tolerance

    def test_create_access_token_default_expiration(self):
        """Test token creation with default expiration"""
        data = {"sub": "testuser"}
        token = create_access_token(data)

        payload = jwt.decode(
            token,
            settings.JWT_SECRET,
            algorithms=[settings.JWT_ALGORITHM],
        )

        # Verify expiration matches settings
        exp_time = datetime.fromtimestamp(payload["exp"])
        expected_exp = datetime.utcnow() + timedelta(minutes=settings.JWT_EXPIRATION_MINUTES)
        time_diff = abs((exp_time - expected_exp).total_seconds())
        assert time_diff < 5

    def test_decode_access_token_valid(self):
        """Test decoding valid token"""
        data = {"sub": "testuser", "custom": "value"}
        token = create_access_token(data)

        decoded = decode_access_token(token)
        assert decoded["sub"] == "testuser"
        assert decoded["custom"] == "value"
        assert "exp" in decoded

    def test_decode_access_token_invalid(self):
        """Test decoding invalid token raises HTTPException"""
        invalid_token = "invalid.token.string"

        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(invalid_token)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Could not validate credentials" in str(exc_info.value.detail)

    def test_decode_access_token_expired(self):
        """Test decoding expired token raises HTTPException"""
        data = {"sub": "testuser"}
        # Create token that expires immediately
        token = create_access_token(data, timedelta(seconds=-1))

        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(token)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    def test_decode_access_token_wrong_secret(self):
        """Test decoding token with wrong secret raises HTTPException"""
        data = {"sub": "testuser"}
        # Create token with different secret
        token = jwt.encode(data, "wrong_secret", algorithm=settings.JWT_ALGORITHM)

        with pytest.raises(HTTPException) as exc_info:
            decode_access_token(token)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED


@pytest.mark.unit
@pytest.mark.asyncio
class TestAuthenticateUser:
    """Test user authentication"""

    async def test_authenticate_user_success(self, sample_user):
        """Test successful user authentication"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = sample_user
        mock_conn.execute = AsyncMock()
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        with patch("app.auth.database.db_pool", mock_pool):
            result = await authenticate_user("testuser", "testpassword")

            assert result is not None
            assert result["username"] == "testuser"
            assert result["id"] == "user-123"

            # Verify last_login was updated
            mock_conn.execute.assert_called_once()
            call_args = mock_conn.execute.call_args[0][0]
            assert "UPDATE users SET last_login" in call_args

    async def test_authenticate_user_wrong_password(self, sample_user):
        """Test authentication with wrong password"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = sample_user
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        with patch("app.auth.database.db_pool", mock_pool):
            result = await authenticate_user("testuser", "wrongpassword")

            assert result is None

    async def test_authenticate_user_not_found(self):
        """Test authentication with non-existent user"""
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = None  # User not found
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        with patch("app.auth.database.db_pool", mock_pool):
            result = await authenticate_user("nonexistent", "password")

            assert result is None

    async def test_authenticate_user_inactive(self, sample_user):
        """Test authentication with inactive user"""
        sample_user["is_active"] = False

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = None  # Inactive users not returned
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        with patch("app.auth.database.db_pool", mock_pool):
            result = await authenticate_user("testuser", "testpassword")

            assert result is None

    async def test_authenticate_user_no_db_connection(self):
        """Test authentication when database is not available"""
        with patch("app.auth.database.db_pool", None):
            with pytest.raises(HTTPException) as exc_info:
                await authenticate_user("testuser", "password")

            assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Database connection not available" in str(exc_info.value.detail)


@pytest.mark.unit
@pytest.mark.asyncio
class TestGetCurrentUser:
    """Test get_current_user dependency"""

    async def test_get_current_user_success(self, sample_user):
        """Test successful current user retrieval"""
        # Create valid token
        token = create_access_token({"sub": sample_user["username"]})
        credentials = MagicMock()
        credentials.credentials = token

        # Mock database
        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = sample_user
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        with patch("app.auth.database.db_pool", mock_pool):
            result = await get_current_user(credentials)

            assert result["username"] == sample_user["username"]
            assert result["id"] == sample_user["id"]

    async def test_get_current_user_invalid_token(self):
        """Test with invalid token"""
        credentials = MagicMock()
        credentials.credentials = "invalid.token.string"

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_get_current_user_missing_username(self):
        """Test token without username (sub) claim"""
        token = create_access_token({"other": "data"})  # No 'sub'
        credentials = MagicMock()
        credentials.credentials = token

        with pytest.raises(HTTPException) as exc_info:
            await get_current_user(credentials)

        assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
        assert "Could not validate credentials" in str(exc_info.value.detail)

    async def test_get_current_user_not_found_in_db(self, sample_user):
        """Test when user in token doesn't exist in database"""
        token = create_access_token({"sub": "nonexistent"})
        credentials = MagicMock()
        credentials.credentials = token

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = None  # User not found
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        with patch("app.auth.database.db_pool", mock_pool):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(credentials)

            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED
            assert "User not found" in str(exc_info.value.detail)

    async def test_get_current_user_inactive_user(self, sample_user):
        """Test with inactive user"""
        sample_user["is_active"] = False
        token = create_access_token({"sub": sample_user["username"]})
        credentials = MagicMock()
        credentials.credentials = token

        mock_pool = MagicMock()
        mock_conn = AsyncMock()
        mock_conn.fetchrow.return_value = None  # Inactive user not returned
        mock_pool.acquire.return_value.__aenter__.return_value = mock_conn

        with patch("app.auth.database.db_pool", mock_pool):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(credentials)

            assert exc_info.value.status_code == status.HTTP_401_UNAUTHORIZED

    async def test_get_current_user_no_db_connection(self, sample_user):
        """Test when database is not available"""
        token = create_access_token({"sub": sample_user["username"]})
        credentials = MagicMock()
        credentials.credentials = token

        with patch("app.auth.database.db_pool", None):
            with pytest.raises(HTTPException) as exc_info:
                await get_current_user(credentials)

            assert exc_info.value.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
            assert "Database connection not available" in str(exc_info.value.detail)


@pytest.mark.unit
@pytest.mark.asyncio
class TestGetCurrentAdminUser:
    """Test get_current_admin_user dependency"""

    async def test_get_current_admin_user_success(self, sample_admin):
        """Test successful admin user verification"""
        result = await get_current_admin_user(sample_admin)

        assert result == sample_admin
        assert result["is_admin"] is True

    async def test_get_current_admin_user_not_admin(self, sample_user):
        """Test with non-admin user"""
        with pytest.raises(HTTPException) as exc_info:
            await get_current_admin_user(sample_user)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN
        assert "Not enough permissions" in str(exc_info.value.detail)

    async def test_get_current_admin_user_missing_is_admin(self):
        """Test with user missing is_admin field"""
        user_without_admin = {"username": "test"}

        with pytest.raises(HTTPException) as exc_info:
            await get_current_admin_user(user_without_admin)

        assert exc_info.value.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.unit
class TestSecurityConfiguration:
    """Test security configuration"""

    def test_security_scheme_configured(self):
        """Test HTTPBearer security scheme is configured"""
        from fastapi.security import HTTPBearer

        assert isinstance(security, HTTPBearer)

    def test_jwt_settings_configured(self):
        """Test JWT settings are properly configured"""
        assert hasattr(settings, "JWT_SECRET")
        assert hasattr(settings, "JWT_ALGORITHM")
        assert hasattr(settings, "JWT_EXPIRATION_MINUTES")
        assert settings.JWT_ALGORITHM == "HS256"
        assert settings.JWT_EXPIRATION_MINUTES > 0
