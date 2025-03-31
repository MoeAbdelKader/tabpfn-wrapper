import logging
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from tabpfn_api.db.database import get_db
from tabpfn_api.models.user import User # Need User model for dependency typing
from tabpfn_api.core.security import get_current_user # Use the updated dependency
from tabpfn_api.schemas.model import ModelFitRequest, ModelFitResponse, ModelPredictRequest, ModelPredictResponse
from tabpfn_api.services.model_service import train_new_model, get_predictions, ModelServiceError

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

@router.post(
    "/{model_id}/predict",
    response_model=ModelPredictResponse,
    status_code=status.HTTP_200_OK,
    summary="Get predictions using a trained model",
    description="Submit feature data to get predictions from a previously trained TabPFN model. "
                "The model must belong to the authenticated user.",
    tags=["Models"]
)
async def predict_with_model(
    model_id: str,
    request_body: ModelPredictRequest,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Handles the request to get predictions from a trained model."""
    try:
        log.info(f"Received prediction request from user ID: {current_user.id} for model: {model_id}")
        
        # Validate model_id is a valid UUID
        try:
            uuid.UUID(model_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid model ID format"
            )

        predictions = await get_predictions(
            db=db,
            current_user=current_user,
            internal_model_id=model_id,
            features=request_body.features,
            task=request_body.task,
            output_type=request_body.output_type,
            config=request_body.config
        )
        
        log.info(f"Successfully generated predictions for model {model_id}")
        return ModelPredictResponse(predictions=predictions)

    except ModelServiceError as e:
        # Handle errors raised from the service layer
        log.error(f"Model service error during prediction request for user {current_user.id}: {e}", exc_info=True)
        
        # Map service errors to appropriate HTTP status codes
        if "not found" in str(e).lower():
            status_code = status.HTTP_404_NOT_FOUND
        elif "access denied" in str(e).lower():
            status_code = status.HTTP_403_FORBIDDEN
        elif "decrypt" in str(e).lower():
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        else:
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE

        raise HTTPException(
            status_code=status_code,
            detail=str(e)
        )
    except Exception as e:
        # Catch any other unexpected errors
        log.exception(f"Unexpected error during prediction request for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected internal error occurred."
        )

# Placeholder for /models endpoint (Milestone 5) 