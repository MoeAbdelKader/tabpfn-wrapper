import logging # Add logging import
from fastapi import FastAPI, status
from fastapi.staticfiles import StaticFiles # <-- Import StaticFiles
from fastapi.templating import Jinja2Templates # <-- Import Jinja2Templates
import os # <-- Import os

# Import and call logging setup first
from tabpfn_api.core.logging_config import setup_logging
setup_logging()

# Now create the app instance
log = logging.getLogger(__name__) # Get a logger for this module
log.info("Starting TabPFN API Wrapper...")

# Create FastAPI app instance
app = FastAPI(
    title="TabPFN API Wrapper",
    description="An API wrapper for the PriorLabs TabPFN client.",
    version="0.1.0",
)

# --- UI Setup ---
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
TEMPLATES_DIR = os.path.join(BASE_DIR, "templates")

# Create static and template directories if they don't exist
# (Useful for initial setup, though typically managed by repo structure)
os.makedirs(STATIC_DIR, exist_ok=True)
os.makedirs(TEMPLATES_DIR, exist_ok=True)

# Mount static files directory
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")

# Setup Jinja2 templates
templates = Jinja2Templates(directory=TEMPLATES_DIR)

# --- End UI Setup ---

# Import database initialization function
from tabpfn_api.db.database import init_db

# Import settings and the auth router
from tabpfn_api.core.config import settings
from tabpfn_api.api import auth as auth_router
from tabpfn_api.api import models as models_router # Import the new models router
# TODO: Add model router import here when created

# --- TEMPORARY: Import and include test router for testing auth dependency ---
# REMOVED - This is now handled in tests/conftest.py
# try:
#     from tests.test_api_auth import test_router as auth_test_router
#     app.include_router(auth_test_router, prefix="/test_auth", tags=["Test Auth"])
#     log.info("Included temporary auth test router.")
# except ImportError:
#     log.info("Auth test router not found, skipping.")
#     pass
# --- END TEMPORARY ---

# --- Import UI Router (Add this later when ui/routes.py is created) ---
from tabpfn_api.ui import routes as ui_router # <-- Import the UI router
app.include_router(ui_router.router, tags=["UI"], include_in_schema=False) # <-- Include the router
# --- End UI Router Import ---

@app.get("/", tags=["General"], status_code=status.HTTP_200_OK)
async def read_root():
    """
    Root endpoint providing a welcome message.
    """
    return {"message": "Welcome to the TabPFN API Wrapper!"}


@app.get("/health", tags=["General"], status_code=status.HTTP_200_OK)
async def health_check():
    """
    Health check endpoint to verify the API is running.
    """
    # In the future, this could check database connections, etc.
    return {"status": "ok"}

# Include API routers
app.include_router(auth_router.router, prefix=f"{settings.API_V1_STR}/auth", tags=["Authentication"])
app.include_router(models_router.router, prefix=f"{settings.API_V1_STR}/models", tags=["Models"]) # Add the models router

# Placeholder for future imports and router includes
# from tabpfn_api.api.v1 import api_router
# app.include_router(api_router, prefix="/api/v1")

# Placeholder for database init, etc. on startup (if needed)
@app.on_event("startup")
async def startup_event():
    log.info("Running startup event...")
    # Import init_db here to avoid circular imports if models load db
    from tabpfn_api.db.database import init_db
    await init_db() # Await the async init_db
    log.info("Startup event finished.")

# Placeholder for cleanup on shutdown (if needed)
# @app.on_event("shutdown")
# async def shutdown_event():
#     pass 