import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from tabpfn_api.db.database import get_db
from tabpfn_api.models.user import User # Need User model for dependency typing
from tabpfn_api.core.security import get_current_user # Use the updated dependency
from tabpfn_api.schemas.model import ModelFitRequest, ModelFitResponse
from tabpfn_api.services.model_service import train_new_model, ModelServiceError

log = logging.getLogger(__name__)
router = APIRouter()

@router.post(
    "/fit",
    response_model=ModelFitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Train a new TabPFN model",
    description="Submit feature and target data to train a new TabPFN model. "
                "Returns an internal model ID for future reference (e.g., prediction).",
    tags=["Models"]
)
async def fit_new_model(
    request_body: ModelFitRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user) # Use the dependency returning User object
):
    """Handles the request to train a new model."""
    try:
        log.info(f"Received model fit request from user ID: {current_user.id}")
        internal_model_id = await train_new_model(
            db=db,
            current_user=current_user,
            features=request_body.features,
            target=request_body.target,
            feature_names=request_body.feature_names,
            config=request_body.config
        )
        log.info(f"Model training successful for user ID: {current_user.id}. Internal ID: {internal_model_id}")
        return ModelFitResponse(internal_model_id=internal_model_id)

    except ModelServiceError as e:
        # Handle errors raised from the service layer
        log.error(f"Model service error during fit request for user {current_user.id}: {e}", exc_info=True)
        # Determine appropriate HTTP status code based on error (optional refinement)
        # For now, map most service errors to 500, but could map specific ones (e.g., bad data) to 400
        if "decrypt" in str(e) or "save model metadata" in str(e):
            detail = "An internal error occurred while processing your request."
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        else: # Assume other errors (like TabPFN failure) are potentially user-related or transient
             # Consider mapping TabPFN client errors (like invalid inputs) to 400 Bad Request here.
             # For now, using 503 Service Unavailable as TabPFN might be the issue.
            detail = f"Failed to train model: {e}"
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE

        raise HTTPException(
            status_code=status_code,
            detail=detail,
        )
    except Exception as e:
        # Catch any other unexpected errors
        log.exception(f"Unexpected error during model fit request for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected internal error occurred.",
        )

# Placeholder for /models/{model_id}/predict endpoint (Milestone 4)

# Placeholder for /models endpoint (Milestone 5) 