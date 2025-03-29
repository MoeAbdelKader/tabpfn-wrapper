import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from tabpfn_api.db.database import get_db
from tabpfn_api.schemas.auth import UserSetupRequest, UserSetupResponse
from tabpfn_api.services.auth_service import (
    setup_user,
    InvalidTabPFNTokenError,
    AuthServiceError,
)

log = logging.getLogger(__name__)
router = APIRouter()


@router.post(
    "/setup",
    response_model=UserSetupResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register TabPFN Token",
    description="Provide your valid TabPFN token to receive a service-specific API key. "
                "This API key should be used in the 'Authorization: Bearer <key>' header "
                "for subsequent requests to protected endpoints.",
    tags=["Authentication"]
)
def register_user(
    request_body: UserSetupRequest,
    db: Session = Depends(get_db)
):
    """Registers a user by validating their TabPFN token and generating a service API key."""
    try:
        api_key = setup_user(db=db, tabpfn_token=request_body.tabpfn_token)
        log.info(f"Successfully registered user.")
        return UserSetupResponse(api_key=api_key)
    except InvalidTabPFNTokenError as e:
        log.warning(f"User registration failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e),
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