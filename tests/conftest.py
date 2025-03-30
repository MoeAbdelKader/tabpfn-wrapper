# tests/conftest.py
import pytest
import pytest_asyncio
import os
from typing import AsyncGenerator

# Use SQLAlchemy async features
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy import text # Needed for raw SQL execution like table creation check

from fastapi import FastAPI
from httpx import AsyncClient, ASGITransport

from tabpfn_api.db.database import Base, get_db
from main import app  # <-- Correctly import app from main.py in the root
from tabpfn_api.core.config import settings
from tests.test_api_auth import test_router as auth_test_router # <-- Import the test router

# Use a separate database for testing
# Use in-memory SQLite with async driver
TEST_DATABASE_URL = "sqlite+aiosqlite:///./test.db" # Keep using async driver

@pytest.fixture(scope="session", autouse=True)
def setup_test_db_file():
    """Fixture to set up and tear down the test database file."""
    db_file = "./test.db"
    if os.path.exists(db_file):
        os.remove(db_file)
    yield
    if os.path.exists(db_file):
        os.remove(db_file)

@pytest.fixture(scope="session")
def async_engine():
    """Creates an SQLAlchemy AsyncEngine for the test database."""
    # Use create_async_engine
    return create_async_engine(TEST_DATABASE_URL, echo=False) # echo=True for debugging SQL

@pytest.fixture(scope="session")
def AsyncTestingSessionLocal(async_engine):
    """Creates an async sessionmaker for the test database."""
    # Use async_sessionmaker
    return async_sessionmaker(async_engine, expire_on_commit=False, class_=AsyncSession)

@pytest_asyncio.fixture(scope="function")
async def db_session(async_engine, AsyncTestingSessionLocal) -> AsyncGenerator[AsyncSession, None]:
    """Yields an AsyncSession for a test, ensuring clean state via drop/create."""
    # Ensure tables are dropped and recreated for each test function for isolation
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all) # Drop existing tables
        await conn.run_sync(Base.metadata.create_all) # Create tables anew

    # Create a session
    async with AsyncTestingSessionLocal() as session:
        yield session # Provide the session to the test
        # Rollback/close handled by context manager

@pytest.fixture(scope="function")
def override_get_db(db_session: AsyncSession):
    """Fixture to override the get_db dependency in the FastAPI app with an AsyncSession."""
    # This assumes the real get_db will also be converted to yield AsyncSession
    # Or that all endpoints using it are covered by tests that use this override.
    async def _override_get_db():
        yield db_session

    original_dependency = app.dependency_overrides.get(get_db)
    app.dependency_overrides[get_db] = _override_get_db
    yield
    if original_dependency:
        app.dependency_overrides[get_db] = original_dependency
    else:
        app.dependency_overrides.pop(get_db, None)

@pytest_asyncio.fixture(scope="function")
async def test_client(override_get_db) -> AsyncGenerator[AsyncClient, None]:
    """Yields an httpx AsyncClient configured for the test app."""
    # Add the test router specifically for the test client
    app.include_router(auth_test_router, prefix="/test_auth", tags=["Test Auth"])

    # Use ASGITransport to test the app directly
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
        yield client

    # Clean up: remove the test router after the test runs
    # REMOVED - Directly modifying app.routes is not allowed/reliable.
    # app.routes = [route for route in app.routes if not hasattr(route, "router") or route.router != auth_test_router] 