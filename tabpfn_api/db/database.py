import logging # Add logging
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker, AsyncSession
from sqlalchemy.orm import declarative_base # Updated import
from typing import AsyncGenerator # Import AsyncGenerator
# Remove sync imports: create_engine, sessionmaker, Session

from tabpfn_api.core.config import settings

log = logging.getLogger(__name__) # Add logger

# Create the SQLAlchemy async engine
# Use future=True for SQLAlchemy 2.0 style operation
async_engine = create_async_engine(
    str(settings.ASYNC_DATABASE_URL), # Assuming ASYNC_DATABASE_URL is defined in settings
    echo=settings.DB_ECHO_LOG, # Control SQL logging via settings
    future=True,
)

# Create an async session factory
AsyncSessionLocal = async_sessionmaker(
    bind=async_engine,
    autocommit=False,
    autoflush=False,
    expire_on_commit=False,
    class_=AsyncSession # Explicitly use AsyncSession
)

# Use the correct import for declarative base in SQLAlchemy 2.0
Base = declarative_base()

# --- Database Initialization (Needs to be async now) ---

async def init_db():
    """Initializes the database asynchronously.
    Use with caution - Alembic is preferred for production.
    """
    # Import models within the async function if needed, or ensure they are loaded
    from tabpfn_api.models import user

    log.info("Initializing database...")
    async with async_engine.begin() as conn:
        # await conn.run_sync(Base.metadata.drop_all) # Optional: drop tables first
        await conn.run_sync(Base.metadata.create_all)
    log.info("Database initialized.")

# --- Async Dependency for FastAPI --- #

async def get_db() -> AsyncGenerator[AsyncSession, None]: # Now AsyncGenerator is defined
    """FastAPI dependency that yields an async SQLAlchemy session."""
    async with AsyncSessionLocal() as session:
        log.debug(f"Yielding database session: {session}")
        try:
            yield session
            # Optional: await session.commit() # Commit if operations within endpoint need it implicitly?
            # Generally better to commit within the endpoint logic itself.
        except Exception as e:
            log.exception("Exception during database session, rolling back.")
            await session.rollback()
            raise # Re-raise the exception after rollback
        finally:
            log.debug(f"Closing database session: {session}")
            # Session is automatically closed by the context manager 