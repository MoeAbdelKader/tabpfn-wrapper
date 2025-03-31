import io
import pytest
import pytest_asyncio
import uuid
from unittest.mock import patch, AsyncMock
import pandas as pd

from httpx import AsyncClient
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from tabpfn_api.models.model import ModelMetadata
from tabpfn_api.core.config import settings
from tabpfn_api.tabpfn_interface.client import TabPFNInterfaceError
from tabpfn_api.services.model_service import CSVParsingError

API_V1_STR = settings.API_V1_STR
MODELS_ENDPOINT = f"{API_V1_STR}/models"

# Test fixture for creating CSV files of different types
@pytest.fixture
def classification_csv_data():
    """Create a simple classification dataset for testing."""
    data = {
        "feature1": [1.0, 2.0, 3.0, 4.0, 5.0],
        "feature2": [0.1, 0.2, 0.3, 0.4, 0.5],
        "label": [0, 1, 0, 1, 0]
    }
    df = pd.DataFrame(data)
    csv_data = io.BytesIO()
    df.to_csv(csv_data, index=False)
    csv_data.seek(0)  # Reset position to beginning
    return csv_data.getvalue()

@pytest.fixture
def prediction_csv_data():
    """Create a simple dataset for prediction (no label column)."""
    data = {
        "feature1": [1.5, 2.5, 3.5],
        "feature2": [0.15, 0.25, 0.35]
    }
    df = pd.DataFrame(data)
    csv_data = io.BytesIO()
    df.to_csv(csv_data, index=False)
    csv_data.seek(0)  # Reset position to beginning
    return csv_data.getvalue()

@pytest.fixture
def invalid_csv_data():
    """Create an invalid CSV for testing error handling."""
    # Deliberately create malformed CSV with header but incomplete rows
    return b"feature1,feature2,label\n1.0,0.1,\n2.0,,0\nthis,is,invalid"

@pytest.mark.asyncio
async def test_csv_upload_train_success(
    test_client: AsyncClient,
    db_session: AsyncSession,
    authenticated_user_token: str,
    classification_csv_data: bytes
):
    """Test successful model training using CSV upload."""
    # Mock the interface function to return a known train_set_uid
    mock_train_set_uid = "mock_tabpfn_uid_csv_123"
    
    with patch("tabpfn_api.services.model_service.fit_model", return_value=mock_train_set_uid) as mock_fit:
        # Create form with file and target_column parameter
        files = {"file": ("test.csv", classification_csv_data, "text/csv")}
        response = await test_client.post(
            f"{MODELS_ENDPOINT}/fit/upload?target_column=label",
            headers={"Authorization": f"Bearer {authenticated_user_token}"},
            files=files
        )
        
    # Check response
    assert response.status_code == status.HTTP_201_CREATED
    response_data = response.json()
    assert "internal_model_id" in response_data
    internal_model_id = response_data["internal_model_id"]
    
    # Verify UUID format
    try:
        uuid.UUID(internal_model_id)
    except ValueError:
        pytest.fail("internal_model_id is not a valid UUID")
    
    # Verify mock was called correctly
    mock_fit.assert_called_once()
    
    # Verify database record was created
    stmt = select(ModelMetadata).where(ModelMetadata.internal_model_id == uuid.UUID(internal_model_id))
    result = await db_session.execute(stmt)
    db_metadata = result.scalar_one_or_none()
    
    assert db_metadata is not None
    assert db_metadata.tabpfn_train_set_uid == mock_train_set_uid
    assert db_metadata.feature_count == 2  # feature1, feature2
    assert db_metadata.sample_count == 5   # 5 rows in our test data
    assert set(db_metadata.feature_names) == {"feature1", "feature2"}

@pytest.mark.asyncio
async def test_csv_upload_train_invalid_target_column(
    test_client: AsyncClient,
    authenticated_user_token: str,
    classification_csv_data: bytes
):
    """Test error handling when target column doesn't exist in CSV."""
    files = {"file": ("test.csv", classification_csv_data, "text/csv")}
    response = await test_client.post(
        f"{MODELS_ENDPOINT}/fit/upload?target_column=nonexistent_column",
        headers={"Authorization": f"Bearer {authenticated_user_token}"},
        files=files
    )
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "target column" in response.json()["detail"].lower()
    assert "nonexistent_column" in response.json()["detail"]

@pytest.mark.asyncio
async def test_csv_upload_train_invalid_csv(
    test_client: AsyncClient,
    authenticated_user_token: str,
    invalid_csv_data: bytes
):
    """Test error handling with malformed CSV data."""
    files = {"file": ("invalid.csv", invalid_csv_data, "text/csv")}
    
    # Use patch to allow the CSVParsingError to bubble up from pandas
    with patch("tabpfn_api.services.model_service.pd.read_csv", side_effect=pd.errors.ParserError("CSV parsing failed")):
        response = await test_client.post(
            f"{MODELS_ENDPOINT}/fit/upload?target_column=label",
            headers={"Authorization": f"Bearer {authenticated_user_token}"},
            files=files
        )
    
    assert response.status_code == status.HTTP_400_BAD_REQUEST
    assert "csv" in response.json()["detail"].lower()
    assert "failed" in response.json()["detail"].lower()

@pytest.mark.asyncio
async def test_csv_upload_train_tabpfn_error(
    test_client: AsyncClient,
    authenticated_user_token: str,
    classification_csv_data: bytes
):
    """Test handling of TabPFNInterfaceError during CSV training."""
    files = {"file": ("test.csv", classification_csv_data, "text/csv")}
    
    # The error should flow through train_model_from_csv to the endpoint
    with patch("tabpfn_api.services.model_service.fit_model", 
               side_effect=TabPFNInterfaceError("TabPFN client error")):
        response = await test_client.post(
            f"{MODELS_ENDPOINT}/fit/upload?target_column=label",
            headers={"Authorization": f"Bearer {authenticated_user_token}"},
            files=files
        )
    
    assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
    assert "tabpfn client error" in response.json()["detail"].lower()

@pytest.mark.asyncio
async def test_csv_upload_predict_success(
    test_client: AsyncClient,
    db_session: AsyncSession,
    authenticated_user_token: str,
    classification_csv_data: bytes,
    prediction_csv_data: bytes
):
    """Test end-to-end CSV upload workflow: train then predict."""
    # First train a model with mock
    mock_train_set_uid = "mock_tabpfn_uid_csv_predict_456"
    
    with patch("tabpfn_api.services.model_service.fit_model", return_value=mock_train_set_uid) as mock_fit:
        files = {"file": ("train.csv", classification_csv_data, "text/csv")}
        train_response = await test_client.post(
            f"{MODELS_ENDPOINT}/fit/upload?target_column=label",
            headers={"Authorization": f"Bearer {authenticated_user_token}"},
            files=files
        )
    
    assert train_response.status_code == status.HTTP_201_CREATED
    model_id = train_response.json()["internal_model_id"]
    
    # Now use it for prediction with mock
    mock_predictions = [0, 1, 0]  # One prediction per row in our test data
    
    with patch("tabpfn_api.services.model_service.predict_model", return_value=mock_predictions) as mock_predict:
        files = {"file": ("predict.csv", prediction_csv_data, "text/csv")}
        predict_response = await test_client.post(
            f"{MODELS_ENDPOINT}/{model_id}/predict/upload?task=classification",
            headers={"Authorization": f"Bearer {authenticated_user_token}"},
            files=files
        )
    
    assert predict_response.status_code == status.HTTP_200_OK
    assert predict_response.json()["predictions"] == mock_predictions
    mock_predict.assert_called_once()

@pytest.mark.asyncio
async def test_csv_upload_predict_column_mismatch(
    test_client: AsyncClient,
    db_session: AsyncSession,
    authenticated_user_token: str,
    classification_csv_data: bytes
):
    """Test prediction fails when CSV columns don't match model's expected features."""
    # First train a model with mock
    mock_train_set_uid = "mock_tabpfn_uid_csv_mismatch_789"
    
    with patch("tabpfn_api.services.model_service.fit_model", return_value=mock_train_set_uid) as mock_fit:
        files = {"file": ("train.csv", classification_csv_data, "text/csv")}
        train_response = await test_client.post(
            f"{MODELS_ENDPOINT}/fit/upload?target_column=label",
            headers={"Authorization": f"Bearer {authenticated_user_token}"},
            files=files
        )
    
    assert train_response.status_code == status.HTTP_201_CREATED
    model_id = train_response.json()["internal_model_id"]
    
    # Create a CSV with wrong number of columns
    data = {
        "feature1": [1.5, 2.5, 3.5],
        "feature2": [0.15, 0.25, 0.35],
        "extra_column": [10, 20, 30]  # This makes 3 columns but model expects 2
    }
    df = pd.DataFrame(data)
    wrong_columns_csv = io.BytesIO()
    df.to_csv(wrong_columns_csv, index=False)
    wrong_columns_csv.seek(0)
    
    # Try to predict with it - should fail with 400 error
    files = {"file": ("wrong_columns.csv", wrong_columns_csv.getvalue(), "text/csv")}
    predict_response = await test_client.post(
        f"{MODELS_ENDPOINT}/{model_id}/predict/upload?task=classification",
        headers={"Authorization": f"Bearer {authenticated_user_token}"},
        files=files
    )
    
    assert predict_response.status_code == status.HTTP_400_BAD_REQUEST
    assert "columns" in predict_response.json()["detail"].lower()
    assert "expected 2" in predict_response.json()["detail"].lower() or "expects 2" in predict_response.json()["detail"].lower()

@pytest.mark.asyncio
async def test_csv_upload_predict_model_not_found(
    test_client: AsyncClient,
    authenticated_user_token: str,
    prediction_csv_data: bytes
):
    """Test prediction with non-existent model ID."""
    non_existent_id = str(uuid.uuid4())
    files = {"file": ("predict.csv", prediction_csv_data, "text/csv")}
    
    response = await test_client.post(
        f"{MODELS_ENDPOINT}/{non_existent_id}/predict/upload?task=classification",
        headers={"Authorization": f"Bearer {authenticated_user_token}"},
        files=files
    )
    
    assert response.status_code == status.HTTP_404_NOT_FOUND
    assert "not found" in response.json()["detail"].lower()

@pytest.mark.asyncio
async def test_csv_upload_predict_no_auth(
    test_client: AsyncClient,
    prediction_csv_data: bytes
):
    """Test prediction endpoint requires authentication."""
    random_id = str(uuid.uuid4())
    files = {"file": ("predict.csv", prediction_csv_data, "text/csv")}
    
    response = await test_client.post(
        f"{MODELS_ENDPOINT}/{random_id}/predict/upload?task=classification",
        files=files
    )
    
    assert response.status_code == status.HTTP_403_FORBIDDEN
    assert "not authenticated" in response.text.lower() 