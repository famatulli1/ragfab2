# Testing Guide - RAGFab

## Overview

RAGFab uses pytest for testing with comprehensive coverage across unit, integration, and E2E tests.

**Target Coverage**: 70% minimum

## Test Structure

```
ragfab/
├── rag-app/
│   ├── tests/
│   │   ├── __init__.py
│   │   ├── conftest.py           # Shared fixtures
│   │   ├── unit/                 # Unit tests
│   │   │   ├── test_embedder.py
│   │   │   └── test_chunker.py
│   │   └── integration/          # Integration tests
│   │       └── test_ingestion_pipeline.py
│   └── pytest.ini
│
└── web-api/
    ├── tests/
    │   ├── __init__.py
    │   ├── conftest.py           # Shared fixtures
    │   ├── unit/                 # Unit tests
    │   │   └── test_auth.py
    │   ├── integration/          # Integration tests
    │   └── e2e/                  # End-to-end tests
    │       └── test_chat_flow.py
    └── pytest.ini
```

## Running Tests

### Quick Start

```bash
# Install test dependencies
cd rag-app && pip install -r requirements.txt
cd ../web-api && pip install -r requirements.txt

# Run all tests
pytest

# Run with coverage
pytest --cov=. --cov-report=html --cov-report=term-missing
```

### By Test Type

```bash
# Unit tests only
pytest -m unit

# Integration tests only
pytest -m integration

# E2E tests only
pytest -m e2e

# Exclude slow tests
pytest -m "not slow"

# Exclude tests requiring embeddings service
pytest -m "not embeddings"
```

### By Component

```bash
# rag-app tests
cd rag-app
pytest tests/

# web-api tests
cd web-api
pytest tests/

# Specific test file
pytest tests/unit/test_embedder.py

# Specific test class
pytest tests/unit/test_embedder.py::TestEmbeddingGeneratorInit

# Specific test function
pytest tests/unit/test_embedder.py::TestEmbeddingGeneratorInit::test_init_defaults
```

### Verbosity Options

```bash
# Verbose output
pytest -v

# Very verbose (show test names)
pytest -vv

# Show print statements
pytest -s

# Show local variables on failure
pytest -l

# Stop on first failure
pytest -x

# Run last failed tests
pytest --lf

# Run failed tests first, then others
pytest --ff
```

## Test Markers

Custom markers for organizing tests:

- `@pytest.mark.unit` - Unit tests
- `@pytest.mark.integration` - Integration tests
- `@pytest.mark.e2e` - End-to-end tests
- `@pytest.mark.slow` - Slow running tests
- `@pytest.mark.embeddings` - Tests requiring embeddings service
- `@pytest.mark.auth` - Authentication tests
- `@pytest.mark.chat` - Chat functionality tests

## Coverage Requirements

### Minimum Coverage: 70%

```bash
# Check coverage meets threshold
pytest --cov=. --cov-fail-under=70

# Generate HTML coverage report
pytest --cov=. --cov-report=html
# Open htmlcov/index.html in browser

# Generate terminal report with missing lines
pytest --cov=. --cov-report=term-missing
```

### Coverage by Component

**rag-app**:
```bash
cd rag-app
pytest --cov=ingestion --cov-report=term-missing
```

**web-api**:
```bash
cd web-api
pytest --cov=app --cov-report=term-missing
```

## Test Configuration

### pytest.ini

Both `rag-app/pytest.ini` and `web-api/pytest.ini` configure:

- Test discovery patterns
- Async test mode (auto)
- Coverage settings
- Default options
- Custom markers

### Environment Variables

**Required for tests**:

```bash
# Database
export DATABASE_URL="postgresql://raguser:testpass@localhost:5432/ragdb_test"

# Embeddings (for integration tests)
export EMBEDDINGS_API_URL="http://localhost:8001"
export EMBEDDING_DIMENSION="1024"

# JWT (for web-api tests)
export JWT_SECRET="test-secret-key"
export JWT_ALGORITHM="HS256"
export JWT_EXPIRATION_MINUTES="30"
```

### Test Database Setup

```bash
# Start test database
docker run -d \
  --name ragfab-postgres-test \
  -e POSTGRES_USER=raguser \
  -e POSTGRES_PASSWORD=testpass \
  -e POSTGRES_DB=ragdb_test \
  -p 5432:5432 \
  pgvector/pgvector:pg16

# Initialize schema
docker exec -i ragfab-postgres-test psql -U raguser -d ragdb_test < database/schema.sql

# Stop and remove when done
docker stop ragfab-postgres-test
docker rm ragfab-postgres-test
```

## Writing Tests

### Unit Test Example

```python
import pytest
from unittest.mock import MagicMock, AsyncMock

@pytest.mark.unit
@pytest.mark.asyncio
class TestMyFeature:
    async def test_something(self):
        """Test description"""
        # Arrange
        mock_obj = MagicMock()

        # Act
        result = await my_function(mock_obj)

        # Assert
        assert result == expected_value
```

### Integration Test Example

```python
@pytest.mark.integration
@pytest.mark.asyncio
async def test_component_integration(mock_embedder, mock_db_conn):
    """Test integration between components"""
    # Use fixtures for dependencies
    result = await process_pipeline(mock_embedder, mock_db_conn)
    assert result["success"] is True
```

### E2E Test Example

```python
@pytest.mark.e2e
def test_user_flow(client, auth_headers):
    """Test complete user flow"""
    # Test API endpoints
    response = client.post(
        "/api/chat",
        headers=auth_headers,
        json={"message": "Hello"},
    )
    assert response.status_code == 200
```

## Mocking Guidelines

### HTTP Requests

```python
with patch("httpx.AsyncClient") as mock_client:
    mock_response = MagicMock()
    mock_response.json.return_value = {"data": "value"}
    mock_client.return_value.__aenter__.return_value.post = AsyncMock(
        return_value=mock_response
    )
```

### Database Connections

```python
with patch("app.auth.database.db_pool") as mock_pool:
    mock_conn = AsyncMock()
    mock_conn.fetchrow.return_value = {"id": "123"}
    mock_pool.acquire.return_value.__aenter__.return_value = mock_conn
```

### Async Functions

```python
mock_func = AsyncMock(return_value="result")
# Or with side effects
mock_func = AsyncMock(side_effect=[result1, result2, Exception("error")])
```

## Fixtures

### Shared Fixtures (conftest.py)

**rag-app**:
- `chunking_config` - Default chunking configuration
- `sample_chunks` - Pre-created document chunks
- `mock_embedder` - Mocked embedding generator
- `mock_db_conn` - Mocked database connection
- `sample_document_content` - Sample markdown content

**web-api**:
- `client` - FastAPI test client
- `mock_db_pool` / `mock_db_conn` - Database mocks
- `sample_user` / `sample_admin` - User fixtures
- `auth_token` / `admin_token` - JWT tokens
- `auth_headers` / `admin_headers` - Authorization headers

### Using Fixtures

```python
def test_my_feature(sample_user, auth_token):
    # Fixtures injected automatically
    assert sample_user["username"] == "testuser"
```

## Continuous Integration

### GitHub Actions

The `.github/workflows/ci.yml` pipeline runs:

1. **Quality Gates**
   - Unit tests (rag-app + web-api)
   - Integration tests
   - Coverage check (70% minimum)

2. **Security Scan**
   - Safety check (dependency vulnerabilities)
   - Bandit scan (code security issues)

3. **Type Checking**
   - Mypy static type analysis

4. **Docker Build**
   - Test all container builds

### Running Locally

```bash
# Simulate CI environment
docker-compose -f docker-compose.test.yml up -d postgres

# Run quality gates
pytest --cov=. --cov-report=term --cov-fail-under=70

# Run security scans
pip install safety bandit
safety check -r requirements.txt
bandit -r . -ll

# Type checking
pip install mypy
mypy . --ignore-missing-imports
```

## Troubleshooting

### Tests Failing

**Import Errors**:
```bash
# Ensure you're in correct directory
cd rag-app  # or web-api
pytest
```

**Async Warnings**:
```bash
# Install pytest-asyncio
pip install pytest-asyncio

# Or add to pytest.ini:
# asyncio_mode = auto
```

**Database Connection Errors**:
```bash
# Check DATABASE_URL is set
echo $DATABASE_URL

# Verify postgres is running
docker ps | grep postgres

# Test connection
psql $DATABASE_URL -c "SELECT 1"
```

### Coverage Not Meeting Threshold

```bash
# See which files need more tests
pytest --cov=. --cov-report=term-missing

# Focus on uncovered lines
pytest --cov=. --cov-report=html
# Open htmlcov/index.html
```

### Slow Tests

```bash
# Show test durations
pytest --durations=10

# Skip slow tests
pytest -m "not slow"
```

## Best Practices

### Test Naming

- Test files: `test_*.py`
- Test classes: `Test*`
- Test functions: `test_*`
- Use descriptive names: `test_user_login_with_invalid_credentials`

### Test Organization

- Group related tests in classes
- One assertion focus per test
- Use arrange-act-assert pattern
- Keep tests independent

### Mocking

- Mock external services (APIs, databases)
- Don't mock the code under test
- Use fixtures for common mocks
- Verify mock calls when important

### Performance

- Mark slow tests with `@pytest.mark.slow`
- Use fixtures with appropriate scope
- Minimize database operations
- Parallelize independent tests

### Maintainability

- Keep tests simple and readable
- Avoid test interdependencies
- Update tests when code changes
- Document complex test setups

## Resources

- [pytest documentation](https://docs.pytest.org/)
- [pytest-asyncio](https://pytest-asyncio.readthedocs.io/)
- [pytest-cov](https://pytest-cov.readthedocs.io/)
- [unittest.mock](https://docs.python.org/3/library/unittest.mock.html)
- [FastAPI testing](https://fastapi.tiangolo.com/tutorial/testing/)
