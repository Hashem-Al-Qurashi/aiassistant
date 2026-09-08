"""Pytest configuration for StratOS."""

import os
import pytest
import pytest_asyncio

# Set test environment BEFORE any backend import
os.environ.setdefault("ENVIRONMENT", "testing")
os.environ.setdefault("OPENAI_API_KEY", "test-key-not-real")
os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///:memory:")


@pytest_asyncio.fixture
async def db_session():
    """Provide an async DB session for tests that need real tables."""
    # Ensure all entity models are registered with Base
    from backend.models import entities  # noqa: F401
    from backend.database import AsyncSessionLocal, Base, engine
    # Ensure tables exist for this session
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        yield session


@pytest.fixture(scope="session", autouse=True)
def setup_test_env():
    """Set up test environment variables (no-op, env vars set above)."""
    yield
