"""Shared fixtures for integration tests.

A throwaway PostgreSQL container is started once per test session via
testcontainers (it is synchronous, so it has no event-loop affinity). The
async engine and session are created per-test to stay within each test's own
event loop, avoiding pytest-asyncio "event loop is closed" errors with
session-scoped async fixtures.

These tests require Docker. They are skipped automatically if the PostgreSQL
container cannot be started.
"""

from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from backend.infrastructure.db.models import Base

try:
    from testcontainers.postgres import PostgresContainer

    _TESTCONTAINERS_AVAILABLE = True
except ImportError:  # pragma: no cover
    _TESTCONTAINERS_AVAILABLE = False


@pytest.fixture(scope="session")
def postgres_url():
    """Start a PostgreSQL container once and yield its asyncpg connection URL."""
    if not _TESTCONTAINERS_AVAILABLE:
        pytest.skip("testcontainers not installed")

    try:
        container = PostgresContainer("postgres:16-alpine", driver="asyncpg")
        container.start()
    except Exception as exc:  # pragma: no cover - Docker not available
        pytest.skip(f"Could not start PostgreSQL container: {exc}")

    try:
        yield container.get_connection_url()
    finally:
        container.stop()


@pytest_asyncio.fixture
async def engine(postgres_url: str):
    """Per-test async engine with a freshly created schema.

    Dropping and recreating all tables gives each test a clean slate and keeps
    the engine within the test's own event loop.
    """
    engine = create_async_engine(postgres_url, pool_pre_ping=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session(engine) -> AsyncGenerator[AsyncSession, None]:
    """Yield a clean async session bound to the per-test engine."""
    factory = async_sessionmaker(bind=engine, class_=AsyncSession, expire_on_commit=False)
    async with factory() as session:
        yield session
