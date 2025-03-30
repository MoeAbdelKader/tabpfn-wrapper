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

# REMOVE the setup_test_user helper function, use the fixture instead
# async def setup_test_user(client: AsyncClient, db: AsyncSession, tabpfn_token: str) -> str:
#    ...

# The test router and protected endpoint (assuming it works with async get_db override)
from fastapi import APIRouter, Depends
from tabpfn_api.core.config import settings # Import settings here
# from tabpfn_api.core.security import get_current_user_token # Already imported

test_router = APIRouter()

@test_router.get("/protected", tags=["Test Auth"])
async def get_protected_resource(
    # Update dependency to use the renamed function get_current_user
    # Also, update the expected type to User (or handle it accordingly)
    # Since this is just a test endpoint, let's keep it simple and just get the user object
    current_user: User = Depends(security.get_current_user) # Updated dependency
):
    """A dummy protected route to test authentication."""
    # We now get the full User object
    # Let's return the user ID for verification
    return {"message": "Access granted", "user_id": current_user.id}

# Assume test_router is mounted by conftest.py

async def test_auth_dependency_success(
    test_client: AsyncClient,
    db_session: AsyncSession, # Keep db_session if needed elsewhere in test or for setup
    authenticated_user_token: str, # Use the fixture
):
    """Test accessing a protected route with a valid API key."""
    api_key = authenticated_user_token # Use the key from the fixture

    # We don't need to query the user directly if the endpoint verifies it.
    # Just hitting the protected endpoint and checking the response is enough.
    # hashed_key = security.get_api_key_hash(api_key)
    # user = await db_session.scalar(select(User).where(User.hashed_api_key == hashed_key))
    # assert user is not None, f"User created by fixture not found for key {api_key}"
    # expected_user_id = user.id

    headers = {"Authorization": f"Bearer {api_key}"}
    response = await test_client.get("/test_auth/protected", headers=headers) # Use test prefix

    assert response.status_code == status.HTTP_200_OK
    data = response.json()
    assert data["message"] == "Access granted"
    assert "user_id" in data # Check that the endpoint returned the user ID
    assert isinstance(data["user_id"], int) # Basic type check for the ID

async def test_auth_dependency_no_token(test_client: AsyncClient):
    """Test accessing protected route without providing a token."""
    response = await test_client.get("/test_auth/protected") # Use test prefix
    # Expect 403 Forbidden when auth header is missing/malformed by default
    assert response.status_code == status.HTTP_403_FORBIDDEN
    # Check the actual detail message returned by FastAPI/Starlette
    assert response.json().get("detail") == "Not authenticated"

async def test_auth_dependency_invalid_scheme(test_client: AsyncClient):
    """Test accessing protected route with incorrect scheme (e.g., Basic)."""
    headers = {"Authorization": "Basic some_token"}
    response = await test_client.get("/test_auth/protected", headers=headers) # Use test prefix
    # Expect 403 Forbidden when scheme is wrong (Based on observed behavior)
    assert response.status_code == status.HTTP_403_FORBIDDEN
    # Expect detail based on observed behavior
    assert response.json().get("detail") == "Invalid authentication credentials"

async def test_auth_dependency_invalid_token(
    test_client: AsyncClient,
    db_session: AsyncSession,
    authenticated_user_token: str # Use the fixture to ensure a user exists
    # Remove mock_verify_tabpfn_token
):
    """Test accessing protected route with an invalid/non-existent API key."""
    # Ensure a user exists via the fixture
    _ = authenticated_user_token

    headers = {"Authorization": "Bearer invalid-api-key"}
    response = await test_client.get("/test_auth/protected", headers=headers) # Use test prefix

    assert response.status_code == status.HTTP_401_UNAUTHORIZED
    assert "Could not validate credentials" in response.json().get("detail", "")

# test_auth_dependency_decryption_error no longer applicable as decryption is not done in the dependency
# Remove or adapt if we want to test decryption failure elsewhere
# async def test_auth_dependency_decryption_error(...) 