import os
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import PostgresDsn, Field, computed_field
from typing import Optional

# Ensure dotenv is loaded if present (useful for local dev outside docker-compose)
try:
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass # Ignore if python-dotenv is not installed


class Settings(BaseSettings):
    """Application configuration settings.

    Loads values from environment variables or a .env file.
    """

    # --- Core Settings ---
    # PostgreSQL Database Connection URL
    # Format (for Cloud Run w/ Auth Proxy): postgresql+psycopg://<user>:<password>@/<database>?host=/cloudsql/<project>:<region>:<instance>
    # NO DEFAULT VALUE - This must be set via environment variable or .env file.
    DATABASE_URL: str

    @computed_field
    @property
    def ASYNC_DATABASE_URL(self) -> str:
        """Computes the async version of the database URL.

        Replaces 'postgresql://' or 'postgresql+psycopg://' with 'postgresql+asyncpg://'
        based on the driver needed for async SQLAlchemy.
        Requires `asyncpg` library to be installed.
        """
        sync_url = str(self.DATABASE_URL)
        if sync_url.startswith("postgresql://"):
            # Replace base scheme with asyncpg
            return sync_url.replace("postgresql://", "postgresql+asyncpg://", 1)
        elif sync_url.startswith("postgresql+psycopg://"): # Handle psycopg scheme
            # Replace psycopg scheme with asyncpg
            return sync_url.replace("postgresql+psycopg://", "postgresql+asyncpg://", 1)
        elif sync_url.startswith("postgresql+psycopg2://"): # Handle psycopg2 scheme
            # Replace psycopg2 scheme with asyncpg
             return sync_url.replace("postgresql+psycopg2://", "postgresql+asyncpg://", 1)
        elif sync_url.startswith("postgresql+asyncpg://"): # Already async
            return sync_url
        else:
            # Raise error if format is unexpected
            raise ValueError(f"Unsupported DATABASE_URL scheme for async conversion: {sync_url}")

    # Secret key for cryptographic operations (e.g., token encryption, JWT)
    # It's CRITICAL to set this via environment variable or .env file.
    # Generate a strong key, e.g., using: openssl rand -hex 32
    # NO DEFAULT VALUE - This must be provided explicitly.
    SECRET_KEY: str

    # --- API Metadata ---
    API_V1_STR: str = "/api/v1"
    PROJECT_NAME: str = "TabPFN API Wrapper"
    PROJECT_VERSION: str = "0.1.0"

    # --- Optional Settings (with defaults) ---
    LOG_LEVEL: str = "INFO"
    DB_ECHO_LOG: bool = False # Add setting to control SQL echoing

    class Config:
        # Load environment variables from a .env file if it exists
        env_file = ".env"
        env_file_encoding = "utf-8"
        # Allow case-insensitive environment variable names
        case_sensitive = False
        # Ignore extra environment variables not defined in the model
        extra = 'ignore'


# Use lru_cache to create a singleton instance of Settings
# This ensures settings are loaded only once
@lru_cache()
def get_settings() -> Settings:
    """Returns the application settings instance."""
    return Settings()


# Expose the settings instance directly for convenience
settings = get_settings() 