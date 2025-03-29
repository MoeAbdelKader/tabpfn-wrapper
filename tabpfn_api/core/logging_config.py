import logging
import sys

from .config import settings


def setup_logging():
    """Configures the root logger for the application."""

    # Get the root logger
    logger = logging.getLogger()

    # Set the log level from settings
    log_level = getattr(logging, settings.LOG_LEVEL.upper(), logging.INFO)
    logger.setLevel(log_level)

    # Create a console handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(log_level)

    # Create a formatter and set it for the handler
    # Example format: 2025-03-29 22:30:00,123 - INFO - module_name - Log message
    formatter = logging.Formatter(
        '%(asctime)s - %(levelname)s - %(name)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    handler.setFormatter(formatter)

    # Add the handler to the root logger
    # Check if handlers already exist to prevent duplicates during reloads
    if not logger.handlers:
        logger.addHandler(handler)
    else:
        # If handlers exist (e.g., due to Uvicorn reload), ensure level is updated
        for h in logger.handlers:
            h.setLevel(log_level)

    # Optional: Adjust log levels for specific libraries if needed
    # logging.getLogger("uvicorn.error").setLevel(logging.WARNING)
    # logging.getLogger("sqlalchemy.engine").setLevel(logging.INFO) # Set to INFO to see SQL

    # Log that logging is configured
    logging.info(f"Logging configured with level: {settings.LOG_LEVEL.upper()}")

# Note: This setup is basic. For more complex scenarios (e.g., JSON logs,
# file logging, integration with logging services), consider libraries like
# loguru or structlog, or more advanced standard logging configurations. 