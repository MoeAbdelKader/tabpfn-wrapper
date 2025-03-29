import logging # Add logging import
from fastapi import FastAPI, status

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


# Placeholder for future imports and router includes
# from tabpfn_api.api.v1 import api_router
# app.include_router(api_router, prefix="/api/v1")

# Placeholder for database init, etc. on startup (if needed)
# @app.on_event("startup")
# async def startup_event():
#     pass

# Placeholder for cleanup on shutdown (if needed)
# @app.on_event("shutdown")
# async def shutdown_event():
#     pass 