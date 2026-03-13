"""
Pytest fixtures for all tests.
Provides:
- async test client (FastAPI TestClient via httpx)
- test database session (real PostgreSQL, isolated per test via transactions)
- mock Ollama adapter (no real LLM calls in unit tests)
"""
import pytest
import pytest_asyncio
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker
from unittest.mock import AsyncMock, patch

from app.main import app
from app.config.database import Base, get_db
from app.config.settings import get_settings

settings = get_settings()


@pytest_asyncio.fixture(scope="session")
async def engine():
    """Create tables once for the entire test session."""
    _engine = create_async_engine(settings.DATABASE_URL, echo=False)
    async with _engine.begin() as conn:
        await conn.execute(__import__("sqlalchemy").text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)
    yield _engine
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
    await _engine.dispose()


@pytest_asyncio.fixture
async def db_session(engine):
    """Provides a transactional DB session that rolls back after each test."""
    async with engine.connect() as conn:
        await conn.begin()
        session = AsyncSession(bind=conn, expire_on_commit=False)
        yield session
        await session.close()
        await conn.rollback()


@pytest_asyncio.fixture
async def client(db_session):
    """FastAPI test client with database dependency overridden."""
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test",
        headers={"X-App-Id": "test-app-id"},
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
def mock_ollama_adapter():
    """Mock Ollama adapter — returns a canned quiz response."""
    from app.adapters.base import AdapterResponse
    mock = AsyncMock()
    mock.generate.return_value = AdapterResponse(
        content='{"questions": [{"id": 1, "type": "mcq", "question": "Test Q?", '
                '"options": {"A": "1", "B": "2", "C": "3", "D": "4"}, '
                '"correct_answer": "A", "explanation": "Test explanation"}]}',
        model="llama3.2",
        provider="ollama",
        input_tokens=100,
        output_tokens=150,
        total_tokens=250,
    )
    return mock


@pytest.fixture
def sample_user_data():
    return {
        "email": "test@example.com",
        "password": "SecurePass123!",
        "full_name": "Test User",
    }
