# tests/test_api_auth.py
import pytest
from unittest.mock import patch, MagicMock
from httpx import AsyncClient
from fastapi import status
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from tabpfn_api.models.user import User
from tabpfn_api.core import security

# Mark all tests in this module as asyncio
pytestmark = pytest.mark.asyncio

# --- Test /auth/setup ---

VALID_TABPFN_TOKEN = "valid-tabpfn-token"
INVALID_TABPFN_TOKEN = "invalid-tabpfn-token"

@pytest.fixture
def mock_verify_tabpfn_token():
    """Mocks the tabpfn_interface.client.verify_tabpfn_token function."""
    with patch('tabpfn_api.services.auth_service.verify_tabpfn_token') as mock_verify:
        mock_verify.side_effect = lambda token: token == VALID_TABPFN_TOKEN
        yield mock_verify

async def test_setup_user_success(
    test_client: AsyncClient,
    db_session: AsyncSession,
    mock_verify_tabpfn_token: MagicMock
):
    """Test successful user setup with a valid TabPFN token."""
    response = await test_client.post(
        f"{settings.API_V1_STR}/auth/setup",
        json={"tabpfn_token": VALID_TABPFN_TOKEN}
    )

    assert response.status_code == status.HTTP_201_CREATED
    data = response.json()
    assert "api_key" in data
    generated_api_key = data["api_key"]
    assert isinstance(generated_api_key, str)
    assert len(generated_api_key) > 20

    mock_verify_tabpfn_token.assert_called_once_with(token=VALID_TABPFN_TOKEN)

    # Verify database state using async session
    result = await db_session.execute(select(User))
    user = result.scalar_one_or_none()
    assert user is not None
    assert security.verify_api_key(generated_api_key, user.hashed_api_key)
    decrypted_token = security.decrypt_token(user.encrypted_tabpfn_token)
    assert decrypted_token == VALID_TABPFN_TOKEN
    # Ensure changes are visible if needed (though session scope might handle this)
    # await db_session.commit()

async def test_setup_user_invalid_token(
    test_client: AsyncClient,
    db_session: AsyncSession,
    mock_verify_tabpfn_token: MagicMock
):
    """Test user setup failure with an invalid TabPFN token."""
    response = await test_client.post(
        f"{settings.API_V1_STR}/auth/setup",
        json={"tabpfn_token": INVALID_TABPFN_TOKEN}
    )

    assert response.status_code == status.HTTP_400_BAD_REQUEST
    data = response.json()
    assert "detail" in data
    assert "provided TabPFN token could not be verified" in data["detail"]

    mock_verify_tabpfn_token.assert_called_once_with(token=INVALID_TABPFN_TOKEN)

    # Verify no user was created
    result = await db_session.execute(select(User))
    user = result.scalar_one_or_none()
    assert user is None

async def test_setup_user_internal_error(
    test_client: AsyncClient,
    db_session: AsyncSession,
    mock_verify_tabpfn_token: MagicMock
):
    """Test user setup failure due to an internal error (e.g., DB issue)."""
    # Simulate an error during DB commit by patching AsyncSession.commit
    # Note: Patching the correct async method is important
    with patch('sqlalchemy.ext.asyncio.AsyncSession.commit', side_effect=Exception("DB commit failed")):
        response = await test_client.post(
            f"{settings.API_V1_STR}/auth/setup",
            json={"tabpfn_token": VALID_TABPFN_TOKEN}
        )

    assert response.status_code == status.HTTP_500_INTERNAL_SERVER_ERROR
    data = response.json()
    assert "detail" in data
    assert "internal error occurred" in data["detail"]

# --- Test Authentication Dependency (get_current_user_token) ---

# Helper function to create a user and get their API key
# Needs to be async and use the async session
async def setup_test_user(client: AsyncClient, db: AsyncSession, tabpfn_token: str) -> str:
    # Use the actual setup service function for consistency? Or endpoint?
    # Using endpoint might be simpler for testing integration
    response = await client.post(
        f"{settings.API_V1_STR}/auth/setup",
        json={"tabpfn_token": tabpfn_token}
    )
    assert response.status_code == status.HTTP_201_CREATED
    api_key = response.json()["api_key"]
    # Commit necessary because the subsequent GET request runs in a different context
    await db.commit() # Commit the session used by the POST request
    return api_key

# The test router and protected endpoint (assuming it works with async get_db override)
from fastapi import APIRouter, Depends
from tabpfn_api.core.config import settings # Import settings here
# from tabpfn_api.core.security import get_current_user_token # Already imported

test_router = APIRouter()

@test_router.get("/protected", tags=["Test Auth"])
async def get_protected_resource(
    user_tabpfn_token: str = Depends(security.get_current_user_token)
):
    """A dummy protected route to test authentication."""
    return {"message": "Access granted", "tabpfn_token_snippet": user_tabpfn_token[:5]}

# Assume test_router is mounted by conftest.py

async def test_auth_dependency_success(
    test_client: AsyncClient,
    db_session: AsyncSession,
    mock_verify_tabpfn_token: MagicMock
):
    """Test accessing a protected route with a valid API key."""
    api_key = await setup_test_user(test_client, db_session, VALID_TABPFN_TOKEN)

    headers = {"Authorization": f"Bearer {api_key}"}
    response = await test_client.get("/test_auth/protected", headers=headers) # Use test prefix

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["message"] == "Access granted"
    assert data["tabpfn_token_snippet"] == VALID_TABPFN_TOKEN[:5]

async def test_auth_dependency_no_token(test_client: AsyncClient):
    """Test accessing protected route without providing a token."""
    response = await test_client.get("/test_auth/protected") # Use test prefix
    # Expect 403 Forbidden when auth header is missing/malformed by default
    assert response.status_code == status.HTTP_403_FORBIDDEN
    # Check detail message (FastAPI/Starlette might change this)
    assert "Not authenticated" in response.json().get("detail", "")

async def test_auth_dependency_invalid_scheme(test_client: AsyncClient):
    """Test accessing protected route with incorrect scheme (e.g., Basic)."""
    headers = {"Authorization": "Basic some_token"}
    response = await test_client.get("/test_auth/protected", headers=headers) # Use test prefix
    # Expect 403 Forbidden when auth header is missing/malformed by default
    assert response.status_code == status.HTTP_403_FORBIDDEN
    # Check the actual detail message returned by FastAPI/Starlette
    assert "Invalid authentication credentials" in response.json().get("detail", "")

async def test_auth_dependency_invalid_token(
    test_client: AsyncClient,
    db_session: AsyncSession,
    mock_verify_tabpfn_token: MagicMock
):
    """Test accessing protected route with an invalid/non-existent API key."""
    await setup_test_user(test_client, db_session, VALID_TABPFN_TOKEN)

    headers = {"Authorization": "Bearer invalid-api-key"}
    response = await test_client.get("/test_auth/protected", headers=headers) # Use test prefix

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Could not validate credentials" in response.json().get("detail", "")

async def test_auth_dependency_decryption_error(
    test_client: AsyncClient,
    db_session: AsyncSession,
    mock_verify_tabpfn_token: MagicMock
):
    """Test scenario where token decryption fails (e.g., SECRET_KEY changed)."""
    api_key = await setup_test_user(test_client, db_session, VALID_TABPFN_TOKEN)

    with patch('tabpfn_api.core.security.decrypt_token', side_effect=security.InvalidToken):
        headers = {"Authorization": f"Bearer {api_key}"}
        response = await test_client.get("/test_auth/protected", headers=headers) # Use test prefix

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Could not validate credentials" in response.json().get("detail", "") 