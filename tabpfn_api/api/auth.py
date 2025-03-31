import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from tabpfn_api.db.database import get_db
from tabpfn_api.schemas.auth import UserSetupRequest, UserSetupResponse
from tabpfn_api.services.auth_service import (
    setup_user,
    InvalidTabPFNTokenError,
    AuthServiceError,
    AuthServiceDownstreamUnavailableError,
)

log = logging.getLogger(__name__)
router = APIRouter()

# Define potential responses for OpenAPI documentation
setup_responses = {
    status.HTTP_201_CREATED: {
        "description": "User successfully registered and API key generated.",
        "model": UserSetupResponse, # Reference the schema model
    },
    status.HTTP_400_BAD_REQUEST: {
        "description": "Invalid TabPFN Token: The provided token could not be verified.",
    },
    status.HTTP_503_SERVICE_UNAVAILABLE: {
        "description": "TabPFN Service Unreachable: Could not verify the token due to a connection issue with the downstream TabPFN service.",
    },
    status.HTTP_500_INTERNAL_SERVER_ERROR: {
        "description": "Internal Server Error: An unexpected error occurred during registration.",
    },
}

@router.post(
    "/setup",
    response_model=UserSetupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register TabPFN Token & Get API Key", # Updated summary
    description=( # Updated description
        "Validates a provided PriorLabs TabPFN token and, if valid, generates a unique "
        "API key for this wrapper service.\n\n"
        "**Process:**\n"
        "1. Verifies the `tabpfn_token` with the TabPFN backend.\n"
        "2. Generates a cryptographically secure API key.\n"
        "3. Hashes the API key for storage.\n"
        "4. Encrypts the original `tabpfn_token` for storage.\n"
        "5. Stores the hashed key and encrypted token.\n"
        "6. Returns the **plain text** API key (store this securely!).\n\n"
        "Use the returned `api_key` in the `Authorization: Bearer <api_key>` header for "
        "all subsequent authenticated requests to this API (e.g., `/models/fit`)."
    ),
    tags=["Authentication"],
    responses=setup_responses # Added responses dictionary
)
async def register_user(
    request_body: UserSetupRequest,
    db: AsyncSession = Depends(get_db)
):
    """Registers a user by validating their TabPFN token and generating a service API key."""
    try:
        api_key = await setup_user(db=db, tabpfn_token=request_body.tabpfn_token)
        log.info(f"Successfully registered user.")
        return UserSetupResponse(api_key=api_key)
    except InvalidTabPFNTokenError as e:
        log.warning(f"User registration failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
        )
    except AuthServiceDownstreamUnavailableError as e:
        log.error(f"User registration failed: Downstream TabPFN service unavailable: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The TabPFN service is currently unavailable. Please try again later.",
        )
    except AuthServiceError as e:
        log.error(f"User registration failed due to internal error: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An internal error occurred during registration.",
        )
    except Exception as e:
        # Catch unexpected errors
        log.exception(f"Unexpected error during user registration: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected internal error occurred.",
        ) 