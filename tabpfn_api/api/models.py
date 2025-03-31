import logging
from fastapi import APIRouter, Depends, HTTPException, status, File, UploadFile, Query
from sqlalchemy.ext.asyncio import AsyncSession
import uuid

from tabpfn_api.db.database import get_db
from tabpfn_api.models.user import User # Need User model for dependency typing
from tabpfn_api.core.security import get_current_user # Use the updated dependency
from tabpfn_api.schemas.model import (
    ModelFitRequest, ModelFitResponse, ModelPredictRequest, ModelPredictResponse,
    AvailableModelsResponse, UserModelListResponse,
    ModelCSVFitRequest, ModelCSVPredictRequest
)
from tabpfn_api.services.model_service import (
    train_new_model, get_predictions, list_available_models,
    list_user_models, # Added list_user_models
    train_model_from_csv, get_predictions_from_csv,
    ModelServiceError, ModelServiceDownstreamUnavailableError, CSVParsingError
)

log = logging.getLogger(__name__)
router = APIRouter()

# --- Responses for Fit Endpoint ---
fit_responses = {
    status.HTTP_201_CREATED: {
        "description": "Model successfully trained and metadata stored.",
        "model": ModelFitResponse,
    },
    status.HTTP_400_BAD_REQUEST: {
        "description": "Invalid Input Data: Features/target dimensions mismatch, or incompatible data types.",
    },
    status.HTTP_401_UNAUTHORIZED: {
        "description": "Authentication Required: Invalid or missing API key.",
    },
    status.HTTP_503_SERVICE_UNAVAILABLE: {
        "description": "Service Unavailable: Error during TabPFN client operation (e.g., connection issue, client error) or internal decryption failure.",
    },
    status.HTTP_500_INTERNAL_SERVER_ERROR: {
        "description": "Internal Server Error: Unexpected error during model training or metadata saving.",
    },
}

@router.post(
    "/fit",
    response_model=ModelFitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Train (Fit) a New TabPFN Model",
    description=(
        "Submits feature data (`features`) and target data (`target`) to train a new TabPFN model "
        "using the PriorLabs service associated with the user's authenticated TabPFN token.\n\n"
        "- Requires authentication via Bearer token (service API key).\n"
        "- Performs basic validation on input dimensions.\n"
        "- Calls the TabPFN client's `fit` method.\n"
        "- Stores metadata about the trained model (feature count, sample count, TabPFN `train_set_uid`).\n"
        "- Returns a unique internal `internal_model_id` (UUID) for this service, which is needed for subsequent predictions."
    ),
    tags=["Models"],
    responses=fit_responses
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

    except ModelServiceDownstreamUnavailableError as e:
        log.error(f"Model fit failed for user {current_user.id}: Downstream TabPFN service unavailable: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The TabPFN service is currently unavailable for model training. Please try again later.",
        )
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

# --- Responses for Predict Endpoint ---
predict_responses = {
    status.HTTP_200_OK: {
        "description": "Predictions successfully generated.",
        "model": ModelPredictResponse,
    },
    status.HTTP_400_BAD_REQUEST: {
        "description": "Invalid Input: Invalid model ID format or incompatible feature data.",
    },
    status.HTTP_401_UNAUTHORIZED: {
        "description": "Authentication Required: Invalid or missing API key.",
    },
    status.HTTP_403_FORBIDDEN: {
        "description": "Access Denied: The authenticated user does not own the requested model.",
    },
    status.HTTP_404_NOT_FOUND: {
        "description": "Model Not Found: The requested model ID does not exist.",
    },
    status.HTTP_503_SERVICE_UNAVAILABLE: {
        "description": "Service Unavailable: Error during TabPFN client prediction operation (e.g., connection issue, client error) or internal decryption failure.",
    },
    status.HTTP_500_INTERNAL_SERVER_ERROR: {
        "description": "Internal Server Error: Unexpected error during prediction process.",
    },
}

@router.post(
    "/{model_id}/predict",
    response_model=ModelPredictResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate Predictions from a Trained Model",
    description=(
        "Uses a previously trained model (identified by `model_id`) to generate predictions "
        "on new feature data (`features`).\n\n"
        "- Requires authentication via Bearer token (service API key).\n"
        "- Verifies that the `model_id` exists and belongs to the authenticated user.\n"
        "- Calls the TabPFN client's `predict` method using the stored `train_set_uid`.\n"
        "- Returns the predictions in the format specified by `task` and `output_type`."
    ),
    tags=["Models"],
    responses=predict_responses
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

    except ModelServiceDownstreamUnavailableError as e:
        log.error(f"Prediction failed for model {model_id} (user {current_user.id}): Downstream TabPFN service unavailable: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The TabPFN service is currently unavailable for prediction. Please try again later.",
        )
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

# --- Responses for List Available Models Endpoint (Corrected) ---
available_responses = {
    status.HTTP_200_OK: {
        "description": "Successfully retrieved the lists of available TabPFN base models.",
        "model": AvailableModelsResponse,
    },
    status.HTTP_500_INTERNAL_SERVER_ERROR: {
        "description": "Internal Server Error: An unexpected error occurred while retrieving the model lists from the client library.",
    },
}

# --- Endpoint: GET /models/available (Corrected) ---

@router.get(
    "/available",
    response_model=AvailableModelsResponse,
    status_code=status.HTTP_200_OK,
    summary="List Available TabPFN Base Models by Task",
    description=(
        "Retrieves lists of the names of the pre-trained TabPFN model systems "
        "available within the client library, categorized by task ('classification', 'regression'). "
        "These are hardcoded in the client library and do **not** represent models trained by users.\n\n"
        "This endpoint does not require authentication."
    ),
    tags=["Models"],
    responses=available_responses
)
async def get_list_of_available_models():
    """Handles the request to list available TabPFN base models by task."""
    try:
        log.info("Received request to list available TabPFN models.")
        model_dict = await list_available_models()
        log.info("Successfully listed available models.")
        return AvailableModelsResponse(available_models=model_dict)
    except ModelServiceError as e:
        log.error(f"Failed to list available models: Service error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An internal error occurred while retrieving the available models lists.",
        )
    except Exception as e:
        # Catch any other unexpected errors
        log.exception(f"Unexpected error listing available models: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected internal server error occurred.",
        )

# --- Responses for List User Models Endpoint ---
user_models_responses = {
    status.HTTP_200_OK: {
        "description": "Successfully retrieved the list of models trained by the user.",
        "model": UserModelListResponse,
    },
    status.HTTP_401_UNAUTHORIZED: {
        "description": "Authentication Required: Invalid or missing API key.",
    },
    status.HTTP_500_INTERNAL_SERVER_ERROR: {
        "description": "Internal Server Error: An unexpected error occurred while retrieving the user's models.",
    },
}

# --- Endpoint: GET /models ---

@router.get(
    "/", # Mount at the root of the /models prefix
    response_model=UserModelListResponse,
    status_code=status.HTTP_200_OK,
    summary="List User's Trained Models",
    description=(
        "Retrieves metadata for all models previously trained and saved by the authenticated user.\n\n"
        "- Requires authentication via Bearer token (service API key).\n"
        "- Returns a list, potentially empty, of model metadata objects."
    ),
    tags=["Models"],
    responses=user_models_responses,
    # Apply authentication dependency here
    dependencies=[Depends(get_current_user)]
)
async def get_user_models_list(
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user) # Need user object to pass to service
):
    """Handles the request to list the authenticated user's trained models."""
    try:
        log.info(f"Received request to list models for user ID: {current_user.id}")
        # Call the service function to get list of ORM objects
        user_model_orm_list = await list_user_models(db=db, current_user=current_user)
        log.info(f"Successfully retrieved {len(user_model_orm_list)} models for user {current_user.id}.")
        # Pydantic automatically maps ORM objects in the list to UserModelMetadataItem
        # when creating the UserModelListResponse due to from_attributes=True
        return UserModelListResponse(models=user_model_orm_list)
    except ModelServiceError as e:
        # Handle potential DB errors from the service layer
        log.error(f"Failed to list models for user {current_user.id}: Service error: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"An internal error occurred while retrieving your models.",
        )
    except Exception as e:
        # Catch any other unexpected errors
        log.exception(f"Unexpected error listing models for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected internal server error occurred.",
        )

# --- Responses for CSV Fit Upload Endpoint ---
fit_upload_responses = {
    status.HTTP_201_CREATED: {
        "description": "CSV file successfully parsed, model trained, and metadata stored.",
        "model": ModelFitResponse,
    },
    status.HTTP_400_BAD_REQUEST: {
        "description": "Invalid Input: CSV parsing failed, target column not found, or TabPFN input requirements not met.",
    },
    status.HTTP_401_UNAUTHORIZED: {
        "description": "Authentication Required: Invalid or missing API key.",
    },
    status.HTTP_503_SERVICE_UNAVAILABLE: {
        "description": "Service Unavailable: Error during TabPFN client operation or internal decryption failure.",
    },
    status.HTTP_500_INTERNAL_SERVER_ERROR: {
        "description": "Internal Server Error: Unexpected error during model training or metadata saving.",
    },
}

@router.post(
    "/fit/upload",
    response_model=ModelFitResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Train (Fit) a New TabPFN Model from CSV Upload",
    description=(
        "Uploads a CSV file, parses it to extract feature data and target data (based on the specified `target_column`), "
        "and trains a new TabPFN model using the PriorLabs service.\n\n"
        "- Requires authentication via Bearer token (service API key).\n"
        "- Requires a CSV file with a header row.\n"
        "- The `target_column` parameter specifies which column to use as the target variable; all other columns are used as features.\n"
        "- Returns a unique internal `internal_model_id` (UUID) for this service, which is needed for subsequent predictions."
    ),
    tags=["Models"],
    responses=fit_upload_responses
)
async def fit_new_model_from_csv(
    file: UploadFile = File(..., description="CSV file with header row containing feature and target data"),
    target_column: str = Query(..., description="Name of the column to use as the target variable"),
    config: dict = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Handles the request to train a new model from a CSV file upload."""
    try:
        log.info(f"Received CSV model fit request from user ID: {current_user.id}")
        
        # Check file size limit (optional, set as needed)
        # file_size = await file.seek(0, 2)  # Go to end to get size
        # await file.seek(0)  # Reset position
        # if file_size > MAX_FILE_SIZE:
        #     raise HTTPException(
        #         status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
        #         detail=f"File too large. Maximum size is {MAX_FILE_SIZE} bytes."
        #     )
        
        # Check file content type (optional, but recommended)
        if not file.content_type in ["text/csv", "application/vnd.ms-excel", "application/csv"]:
            log.warning(f"User {current_user.id} uploaded file with unexpected content type: {file.content_type}")
            # Continue processing but log the warning - content type is often unreliable
        
        internal_model_id = await train_model_from_csv(
            db=db,
            current_user=current_user,
            file=file,
            target_column=target_column,
            config=config
        )
        log.info(f"CSV model training successful for user ID: {current_user.id}. Internal ID: {internal_model_id}")
        return ModelFitResponse(internal_model_id=internal_model_id)

    except CSVParsingError as e:
        log.error(f"CSV parsing error for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ModelServiceDownstreamUnavailableError as e:
        log.error(f"CSV model fit failed for user {current_user.id}: Downstream TabPFN service unavailable: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The TabPFN service is currently unavailable for model training. Please try again later.",
        )
    except ModelServiceError as e:
        log.error(f"Model service error during CSV fit request for user {current_user.id}: {e}", exc_info=True)
        if "decrypt" in str(e) or "save model metadata" in str(e):
            detail = "An internal error occurred while processing your request."
            status_code = status.HTTP_500_INTERNAL_SERVER_ERROR
        else:
            detail = f"Failed to train model: {e}"
            status_code = status.HTTP_503_SERVICE_UNAVAILABLE

        raise HTTPException(
            status_code=status_code,
            detail=detail,
        )
    except Exception as e:
        log.exception(f"Unexpected error during CSV model fit request for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected internal error occurred.",
        )

# --- Responses for CSV Predict Upload Endpoint ---
predict_upload_responses = {
    status.HTTP_200_OK: {
        "description": "CSV file successfully parsed and predictions generated.",
        "model": ModelPredictResponse,
    },
    status.HTTP_400_BAD_REQUEST: {
        "description": "Invalid Input: CSV parsing failed, invalid model ID format, or feature mismatch.",
    },
    status.HTTP_401_UNAUTHORIZED: {
        "description": "Authentication Required: Invalid or missing API key.",
    },
    status.HTTP_403_FORBIDDEN: {
        "description": "Access Denied: The authenticated user does not own the requested model.",
    },
    status.HTTP_404_NOT_FOUND: {
        "description": "Model Not Found: The requested model ID does not exist.",
    },
    status.HTTP_503_SERVICE_UNAVAILABLE: {
        "description": "Service Unavailable: Error during TabPFN client prediction operation or internal decryption failure.",
    },
    status.HTTP_500_INTERNAL_SERVER_ERROR: {
        "description": "Internal Server Error: Unexpected error during prediction process.",
    },
}

@router.post(
    "/{model_id}/predict/upload",
    response_model=ModelPredictResponse,
    status_code=status.HTTP_200_OK,
    summary="Generate Predictions from a Trained Model Using CSV Upload",
    description=(
        "Uploads a CSV file containing feature data and uses a previously trained model (identified by `model_id`) "
        "to generate predictions.\n\n"
        "- Requires authentication via Bearer token (service API key).\n"
        "- Requires a CSV file with a header row. The file should contain only feature columns (no target column).\n"
        "- Verifies that the model exists and belongs to the authenticated user.\n"
        "- Validates that the number of columns in the CSV matches the number of features used during training.\n"
        "- Returns the predictions in the format specified by `task` and `output_type`."
    ),
    tags=["Models"],
    responses=predict_upload_responses
)
async def predict_with_model_from_csv(
    model_id: str,
    file: UploadFile = File(..., description="CSV file with header row containing feature data for prediction"),
    task: str = Query(..., description="Task type: 'classification' or 'regression'. Must match the task the model was trained for."),
    output_type: str = Query("mean", description="Specifies output format for regression tasks."),
    config: dict = None,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Handles the request to get predictions from a trained model using a CSV file upload."""
    try:
        log.info(f"Received CSV prediction request from user ID: {current_user.id} for model: {model_id}")
        
        # Validate model_id is a valid UUID
        try:
            uuid.UUID(model_id)
        except ValueError:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Invalid model ID format"
            )
        
        # Check file content type (optional, but recommended)
        if not file.content_type in ["text/csv", "application/vnd.ms-excel", "application/csv"]:
            log.warning(f"User {current_user.id} uploaded file with unexpected content type: {file.content_type}")
            # Continue processing but log the warning - content type is often unreliable
            
        predictions = await get_predictions_from_csv(
            db=db,
            current_user=current_user,
            internal_model_id=model_id,
            file=file,
            task=task,
            output_type=output_type,
            config=config
        )
        
        log.info(f"Successfully generated predictions from CSV for model {model_id}")
        return ModelPredictResponse(predictions=predictions)

    except CSVParsingError as e:
        log.error(f"CSV parsing error for user {current_user.id}, model {model_id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )
    except ModelServiceDownstreamUnavailableError as e:
        log.error(f"CSV prediction failed for model {model_id} (user {current_user.id}): Downstream TabPFN service unavailable: {e}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="The TabPFN service is currently unavailable for prediction. Please try again later.",
        )
    except ModelServiceError as e:
        log.error(f"Model service error during CSV prediction request for user {current_user.id}: {e}", exc_info=True)
        
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
        log.exception(f"Unexpected error during CSV prediction request for user {current_user.id}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected internal error occurred."
        )

# Placeholder for GET /models endpoint (Milestone 5) 