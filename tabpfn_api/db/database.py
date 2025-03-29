from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session

from tabpfn_api.core.config import settings

# Create the SQLAlchemy engine using the database URL from settings
# pool_pre_ping=True checks connections for liveness before handing them out
engine = create_engine(
    str(settings.DATABASE_URL), # Explicitly convert PostgresDsn to string
    pool_pre_ping=True,
    # Add connect_args if needed for specific driver options (e.g., SSL)
    # connect_args={"check_same_thread": False} # Only needed for SQLite
)

# Create a configured "Session" class
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

# Create a Base class for declarative class definitions
Base = declarative_base()

# --- Database Initialization (Optional - for simple cases/initial setup) ---

def init_db():
    """Initializes the database by creating tables based on the defined models.

    NOTE: For production and evolving schemas, use Alembic migrations instead.
          This function is primarily for initial setup or simple scenarios.
    """
    # Import all modules here that might define models so that
    # they will be registered properly on the metadata. Otherwise
    # you will have to import them first before calling init_db()
    # flake8: noqa: F401
    from tabpfn_api.models import user # Import your models here

    print("Initializing database...")
    Base.metadata.create_all(bind=engine)
    print("Database initialized.")

# --- Dependency for FastAPI --- #

def get_db() -> Session:
    """FastAPI dependency to get a database session.

    Yields a SQLAlchemy session and ensures it's closed afterward.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close() 