import os
from functools import lru_cache
from pydantic_settings import BaseSettings
from pydantic import PostgresDsn, Field

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
    # Format: postgresql://<user>:<password>@<host>:<port>/<database>
    # NO DEFAULT VALUE - This must be set via environment variable or .env file.
    DATABASE_URL: PostgresDsn

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

    class Config:
        # Load environment variables from a .env file if it exists
        env_file = ".env"
        env_file_encoding = "utf-8"
        # Allow case-insensitive environment variable names
        case_sensitive = False


# Use lru_cache to create a singleton instance of Settings
# This ensures settings are loaded only once
@lru_cache()
def get_settings() -> Settings:
    """Returns the application settings instance."""
    return Settings()


# Expose the settings instance directly for convenience
settings = get_settings() 