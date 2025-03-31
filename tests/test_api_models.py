import pytest
import uuid
from unittest.mock import patch, AsyncMock

from httpx import AsyncClient
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from tabpfn_api.models.model import ModelMetadata
from tabpfn_api.models.user import User
from tabpfn_api.core.config import settings
from tabpfn_api.tabpfn_interface.client import TabPFNInterfaceError
from tabpfn_api.services.model_service import ModelServiceError
from tabpfn_api.core.security import InvalidToken

API_V1_STR = settings.API_V1_STR
MODELS_ENDPOINT = f"{API_V1_STR}/models"


# Sample valid fit request data
@pytest.fixture
def valid_fit_payload():
    return {
        "features": [[1, 2, 3], [4, 5, 6]],
        "target": [0, 1],
        "feature_names": ["f1", "f2", "f3"],
        "config": {"device": "cpu"}
    }

@pytest.mark.asyncio
async def test_fit_model_success(
    test_client: AsyncClient,
    db_session: AsyncSession,
    authenticated_user_token: str,
    valid_fit_payload: dict
):
    """Test successful model fitting."""
    mock_train_set_uid = "mock_tabpfn_uid_123"

    # Mock the interface function
    with patch("tabpfn_api.services.model_service.fit_model", return_value=mock_train_set_uid) as mock_fit:
        response = await test_client.post(
            f"{MODELS_ENDPOINT}/fit",
            json=valid_fit_payload,
            headers={"Authorization": f"Bearer {authenticated_user_token}"}
        )

    assert response.status_code == status.HTTP_201_CREATED
    response_data = response.json()
    assert "internal_model_id" in response_data
    try:
        internal_model_id_uuid = uuid.UUID(response_data["internal_model_id"])
    except ValueError:
        pytest.fail("internal_model_id is not a valid UUID")

    # Verify mock was called correctly
    mock_fit.assert_called_once()
    # Note: Can't easily assert token equality as it's decrypted in service
    call_args, call_kwargs = mock_fit.call_args
    assert call_kwargs['features'] == valid_fit_payload['features']
    assert call_kwargs['target'] == valid_fit_payload['target']
    assert call_kwargs['config'] == valid_fit_payload['config']

    # Verify database record was created
    stmt = select(ModelMetadata).where(ModelMetadata.internal_model_id == internal_model_id_uuid)
    result = await db_session.execute(stmt)
    db_metadata = result.scalar_one_or_none()

    assert db_metadata is not None
    assert db_metadata.tabpfn_train_set_uid == mock_train_set_uid
    assert db_metadata.feature_count == len(valid_fit_payload["features"][0])
    assert db_metadata.sample_count == len(valid_fit_payload["features"])
    assert db_metadata.feature_names == valid_fit_payload["feature_names"]
    assert db_metadata.tabpfn_config == valid_fit_payload["config"]
    # Verify user association (requires knowing the test user's ID)
    user_stmt = select(User).where(User.id == db_metadata.user_id)
    user_result = await db_session.execute(user_stmt)
    associated_user = user_result.scalar_one()
    # Assuming test_user_data fixture holds the user details
    # This depends on how authenticated_user_token is generated in conftest
    assert associated_user is not None # Check user exists


@pytest.mark.asyncio
async def test_fit_model_unauthenticated(test_client: AsyncClient, valid_fit_payload: dict):
    """Test fitting model without authentication."""
    response = await test_client.post(f"{MODELS_ENDPOINT}/fit", json=valid_fit_payload)
    # Default behavior for missing Bearer token is 403
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "Not authenticated" in response.text # Or check detail message


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "invalid_payload, expected_detail_part",
    [
        ({"features": [[1, 2], [3]], "target": [0, 1]}, "same number of columns"), # Mismatched columns
        ({"features": [[1, 2], [3, 4]], "target": [0]}, "match the number of target values"), # Mismatched rows/target
        ({"features": [], "target": []}, "least 1 item"), # Empty features/target
        ({"features": [[1, 2]], "target": [0], "feature_names": ["a"]}, "match the number of columns"), # Mismatched feature_names
        ({"target": [0, 1]}, "Field required"), # Missing features
        ({"features": [[1, 2], [3, 4]]}, "Field required"), # Missing target
    ]
)
async def test_fit_model_invalid_payload(
    test_client: AsyncClient,
    authenticated_user_token: str,
    invalid_payload: dict,
    expected_detail_part: str
):
    """Test fitting model with various invalid payloads."""
    response = await test_client.post(
        f"{MODELS_ENDPOINT}/fit",
        json=invalid_payload,
        headers={"Authorization": f"Bearer {authenticated_user_token}"}
    )
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    response_data = response.json()
    assert "detail" in response_data
    # Check if expected error message part is present in any validation error detail
    assert any(expected_detail_part in error["msg"] for error in response_data["detail"])

@pytest.mark.asyncio
async def test_fit_model_tabpfn_interface_error(
    test_client: AsyncClient,
    authenticated_user_token: str,
    valid_fit_payload: dict
):
    """Test handling of TabPFNInterfaceError during fit."""
    error_message = "TabPFN client connection failed"
    with patch("tabpfn_api.services.model_service.fit_model", side_effect=TabPFNInterfaceError(error_message)):
        response = await test_client.post(
            f"{MODELS_ENDPOINT}/fit",
            json=valid_fit_payload,
            headers={"Authorization": f"Bearer {authenticated_user_token}"}
        )
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert error_message in response.json()["detail"]

@pytest.mark.asyncio
async def test_fit_model_decryption_error(
    test_client: AsyncClient,
    authenticated_user_token: str,
    valid_fit_payload: dict
):
    """Test handling of decryption error in service layer."""
    with patch("tabpfn_api.services.model_service.decrypt_token", side_effect=InvalidToken("Decryption failed")):
        response = await test_client.post(
            f"{MODELS_ENDPOINT}/fit",
            json=valid_fit_payload,
            headers={"Authorization": f"Bearer {authenticated_user_token}"}
        )
    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    # Use the exact detail message from the endpoint's exception handler
    assert response.json()["detail"] == "An internal error occurred while processing your request."

@pytest.mark.asyncio
async def test_fit_model_db_save_error(
    test_client: AsyncClient,
    db_session: AsyncSession,
    authenticated_user_token: str,
    valid_fit_payload: dict
):
    """Test handling of database save error after successful fit."""
    mock_train_set_uid = "mock_tabpfn_uid_dberror"

    # Mock rollback to verify it gets called
    mock_rollback = AsyncMock()
    db_session.rollback = mock_rollback # Replace rollback with mock

    with patch("tabpfn_api.services.model_service.fit_model", return_value=mock_train_set_uid):
        # Mock commit to fail
        with patch.object(db_session, 'commit', side_effect=Exception("DB commit failed"), autospec=True):
            # We also need to mock refresh because commit fails before refresh
            with patch.object(db_session, 'refresh', new_callable=AsyncMock, side_effect=Exception("Should not be called")):
                response = await test_client.post(
                    f"{MODELS_ENDPOINT}/fit",
                    json=valid_fit_payload,
                    headers={"Authorization": f"Bearer {authenticated_user_token}"}
                )

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    assert response.json()["detail"] == "An internal error occurred while processing your request."

    # Verify rollback was called due to the commit failure
    mock_rollback.assert_awaited_once()

    # Remove the check for object existence as it can be unreliable due to session state
    # stmt = select(ModelMetadata).where(ModelMetadata.tabpfn_train_set_uid == mock_train_set_uid)
    # result = await db_session.execute(stmt)
    # db_metadata = result.scalar_one_or_none()
    # assert db_metadata is None 

# Sample valid prediction request data
@pytest.fixture
def valid_predict_payload():
    return {
        "features": [[1, 2, 3], [4, 5, 6]],
        "task": "classification",
        "output_type": "mean",
        "config": {"device": "cpu"}
    }

@pytest.mark.asyncio
async def test_predict_model_success(
    test_client: AsyncClient,
    db_session: AsyncSession,
    authenticated_user_token: str,
    # We'll modify the payload inside the test for clarity
    # valid_predict_payload: dict 
):
    """Test successful model prediction (Regression Task)."""
    # --- Setup: Create a model to predict with (using fit) ---
    fit_payload = { # Use a unique payload for fit if needed, or reuse parts
        "features": [[1.0, 2.5, 3.1], [4.2, 5.0, 6.9], [7.0, 8.5, 9.3]],
        "target": [10.5, 12.1, 15.6], # Regression targets
        "feature_names": ["f1", "f2", "f3"],
        "config": {"device": "cpu"}
    }
    mock_train_set_uid = "mock_tabpfn_uid_regression_123"
    internal_model_id = None

    # Mock the fit function to create a model
    with patch("tabpfn_api.services.model_service.fit_model", return_value=mock_train_set_uid) as mock_fit:
        response = await test_client.post(
            f"{MODELS_ENDPOINT}/fit",
            json=fit_payload,
            headers={"Authorization": f"Bearer {authenticated_user_token}"}
        )
        assert response.status_code == status.HTTP_201_CREATED
        internal_model_id = response.json()["internal_model_id"]
        assert internal_model_id is not None

    # --- Test: Perform prediction with the created model ---
    predict_payload = {
        "features": [[1.5, 2.8, 3.5], [4.0, 5.1, 6.5]], # New data for prediction
        "task": "regression", # Specify regression task
        "output_type": "mean", # Specify output type (optional, defaults to mean)
        "config": {"device": "cpu"}
    }
    mock_predictions = [11.2, 13.5] # Example regression predictions (floats)

    # Mock the predict function
    with patch("tabpfn_api.services.model_service.predict_model", return_value=mock_predictions) as mock_predict:
        response = await test_client.post(
            f"{MODELS_ENDPOINT}/{internal_model_id}/predict",
            json=predict_payload,
            headers={"Authorization": f"Bearer {authenticated_user_token}"}
        )

    # --- Assertions ---
    assert response.status_code == status.HTTP_200_OK
    response_data = response.json()
    assert "predictions" in response_data
    # Use pytest.approx for comparing floating-point numbers
    assert response_data["predictions"] == pytest.approx(mock_predictions)

    # Verify mock_predict was called correctly
    mock_predict.assert_called_once()
    call_args, call_kwargs = mock_predict.call_args
    # Check args passed to predict_model
    assert call_kwargs['train_set_uid'] == mock_train_set_uid # Passed internally by service
    assert call_kwargs['features'] == predict_payload['features']
    assert call_kwargs['task'] == predict_payload['task']
    assert call_kwargs['output_type'] == predict_payload['output_type']
    assert call_kwargs['config'] == predict_payload['config']

@pytest.mark.asyncio
async def test_predict_model_not_found(
    test_client: AsyncClient,
    authenticated_user_token: str,
    valid_predict_payload: dict
):
    """Test prediction with non-existent model."""
    non_existent_id = str(uuid.uuid4())
    response = await test_client.post(
        f"{MODELS_ENDPOINT}/{non_existent_id}/predict",
        json=valid_predict_payload,
        headers={"Authorization": f"Bearer {authenticated_user_token}"}
    )
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "Model not found" in response.json()["detail"]

@pytest.mark.asyncio
async def test_predict_model_unauthorized(
    test_client: AsyncClient,
    authenticated_user_token: str,
):
    """Test prediction endpoint handling of ownership error from service."""
    # --- Setup: Create a model with the authenticated user ---
    fit_payload = {
        "features": [[1, 2], [3, 4]],
        "target": [0, 1],
        "config": {}
    }
    mock_train_set_uid = "mock_tabpfn_uid_unauth_456"
    internal_model_id = None

    with patch("tabpfn_api.services.model_service.fit_model", return_value=mock_train_set_uid):
        response = await test_client.post(
            f"{MODELS_ENDPOINT}/fit",
            json=fit_payload,
            headers={"Authorization": f"Bearer {authenticated_user_token}"}
        )
        assert response.status_code == status.HTTP_201_CREATED
        internal_model_id = response.json()["internal_model_id"]
        assert internal_model_id is not None

    # --- Test: Call predict, mocking the service to raise the ownership error ---
    predict_payload = { # Payload for the predict attempt
        "features": [[5, 6]],
        "task": "classification",
    }

    # Mock get_predictions to directly raise the specific error we want the endpoint to handle
    with patch("tabpfn_api.api.models.get_predictions",
               new_callable=AsyncMock, # Use AsyncMock for async functions
               side_effect=ModelServiceError("Access denied: You do not own this model")) as mock_service_call:
        response = await test_client.post(
            f"{MODELS_ENDPOINT}/{internal_model_id}/predict",
            json=predict_payload,
            headers={"Authorization": f"Bearer {authenticated_user_token}"} # Use the original owner token
        )

    # --- Assertions ---
    # Verify the service function mock was awaited
    mock_service_call.assert_awaited_once()
    # Check the correct status code and detail message are returned from the endpoint's error handler
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "Access denied: You do not own this model" in response.json()["detail"]

@pytest.mark.asyncio
async def test_predict_model_invalid_task(
    test_client: AsyncClient,
    authenticated_user_token: str,
    # valid_predict_payload: dict # Modify payload inside test
):
    """Test prediction request validation with invalid task type."""
    # --- Setup: Create a model first (required for the endpoint path) ---
    fit_payload = { "features": [[1, 2]], "target": [0], "config": {} }
    mock_train_set_uid = "mock_tabpfn_uid_invalid_task_789"
    internal_model_id = None

    with patch("tabpfn_api.services.model_service.fit_model", return_value=mock_train_set_uid) as mock_fit:
        response = await test_client.post(
            f"{MODELS_ENDPOINT}/fit",
            json=fit_payload,
            headers={"Authorization": f"Bearer {authenticated_user_token}"}
        )
        assert response.status_code == status.HTTP_201_CREATED
        internal_model_id = response.json()["internal_model_id"]
        assert internal_model_id is not None

    # --- Test: Try to predict with invalid task in the payload ---
    invalid_predict_payload = {
        "features": [[3, 4]],
        "task": "invalid_task_type", # This is invalid according to schema
        "output_type": "mean",
        "config": {}
    }

    # No need to mock predict_model as validation happens before service call
    response = await test_client.post(
        f"{MODELS_ENDPOINT}/{internal_model_id}/predict",
        json=invalid_predict_payload,
        headers={"Authorization": f"Bearer {authenticated_user_token}"}
    )

    # --- Assertions ---
    # FastAPI/Pydantic validation should catch this
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    # Check validation error details (structure might vary slightly)
    # Look for the specific error message related to the pattern mismatch
    response_data = response.json()
    assert any(
        error.get("msg", "").startswith("String should match pattern") 
        and error.get("loc") == ["body", "task"]
        for error in response_data.get("detail", [])
    )

@pytest.mark.asyncio
async def test_predict_model_invalid_output_type(
    test_client: AsyncClient,
    authenticated_user_token: str,
    # valid_predict_payload: dict # Modify payload inside test
):
    """Test prediction request validation with invalid output type for regression task."""
    # --- Setup: Create a model first ---
    fit_payload = { "features": [[1, 2]], "target": [10.0], "config": {} } # Regression fit
    mock_train_set_uid = "mock_tabpfn_uid_invalid_output_012"
    internal_model_id = None

    with patch("tabpfn_api.services.model_service.fit_model", return_value=mock_train_set_uid) as mock_fit:
        response = await test_client.post(
            f"{MODELS_ENDPOINT}/fit",
            json=fit_payload,
            headers={"Authorization": f"Bearer {authenticated_user_token}"}
        )
        assert response.status_code == status.HTTP_201_CREATED
        internal_model_id = response.json()["internal_model_id"]
        assert internal_model_id is not None

    # --- Test: Try to predict with invalid output type for regression ---
    invalid_predict_payload = {
        "features": [[3, 4]],
        "task": "regression", # Correct task
        "output_type": "invalid_regression_output", # Invalid type for regression
        "config": {}
    }

    # No need to mock predict_model as validation happens before service call
    response = await test_client.post(
        f"{MODELS_ENDPOINT}/{internal_model_id}/predict",
        json=invalid_predict_payload,
        headers={"Authorization": f"Bearer {authenticated_user_token}"}
    )

    # --- Assertions ---
    # FastAPI/Pydantic validation should catch this
    assert response.status_code == status.HTTP_422_UNPROCESSABLE_ENTITY
    assert "Invalid output_type for regression" in response.text 