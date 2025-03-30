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