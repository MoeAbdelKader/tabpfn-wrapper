import base64
from cryptography.fernet import Fernet, InvalidToken
from passlib.context import CryptContext
import secrets
import logging
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select

from tabpfn_api.core.config import settings
from tabpfn_api.db.database import get_db
from tabpfn_api.models.user import User

# --- API Key Hashing (using Passlib) ---

# Configure the hashing context - bcrypt is recommended
# `schemes` defines the allowed hashing algorithms
# `deprecated="auto"` allows older hashes to be verified and upgraded if needed
pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_api_key(plain_api_key: str, hashed_api_key: str) -> bool:
    """Verifies a plain API key against its stored hash."""
    return pwd_context.verify(plain_api_key, hashed_api_key)

def get_api_key_hash(plain_api_key: str) -> str:
    """Hashes an API key using the configured context."""
    return pwd_context.hash(plain_api_key)

def generate_api_key() -> str:
    """Generates a secure, URL-safe random API key."""
    # Generates a 32-byte (256-bit) random key, resulting in a 43-character URL-safe string
    return secrets.token_urlsafe(32)

# --- TabPFN Token Encryption (using Cryptography Fernet) ---

# Derive a Fernet key from the main SECRET_KEY
# Ensure the SECRET_KEY is base64-encoded 32 bytes for Fernet
# We need to handle cases where SECRET_KEY might not be exactly 32 bytes
# Let's use the first 32 bytes if it's longer, and error if shorter.

def _get_fernet_key() -> bytes:
    """Derives a valid Fernet key from the application's SECRET_KEY."""
    secret_key_bytes = settings.SECRET_KEY.encode('utf-8')
    # Use first 32 bytes and encode to base64
    if len(secret_key_bytes) < 32:
        raise ValueError("SECRET_KEY must be at least 32 bytes long for Fernet encryption.")
    # Take the first 32 bytes and base64 encode them
    fernet_key = base64.urlsafe_b64encode(secret_key_bytes[:32])
    return fernet_key

try:
    fernet = Fernet(_get_fernet_key())
except ValueError as e:
    # Handle error during initialization (e.g., log and exit or raise critical error)
    # For now, re-raise to prevent startup if key is invalid
    raise RuntimeError(f"Failed to initialize Fernet encryption: {e}") from e

def encrypt_token(token: str) -> bytes:
    """Encrypts a TabPFN token using Fernet."""
    return fernet.encrypt(token.encode('utf-8'))

def decrypt_token(encrypted_token: bytes) -> str:
    """Decrypts a TabPFN token using Fernet.

    Raises:
        InvalidToken: If the token cannot be decrypted (invalid key or corrupted data).
    """
    try:
        decrypted_bytes = fernet.decrypt(encrypted_token)
        return decrypted_bytes.decode('utf-8')
    except InvalidToken:
        # Re-raise or handle appropriately (e.g., log and return None or raise specific app error)
        # Re-raising for now indicates a serious issue with stored data or key mismatch.
        raise InvalidToken("Could not decrypt token. Key mismatch or data corruption.")

log = logging.getLogger(__name__)

# Define the bearer scheme
bearer_scheme = HTTPBearer(
    scheme_name="Bearer",
    description="Your service-specific API key issued via /auth/setup."
)

async def get_current_user(
    token: HTTPAuthorizationCredentials = Depends(bearer_scheme),
    db: AsyncSession = Depends(get_db)
) -> User:
    """FastAPI dependency to authenticate requests and return the authenticated User object.

    Retrieves the Bearer token, finds the corresponding user by comparing hashes.
    The User object contains the ID and the encrypted TabPFN token.

    Raises:
        HTTPException(401): If the token is invalid, missing, or the user is not found.
        HTTPException(500): For internal errors during authentication.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )

    plain_api_key = token.credentials
    log.debug(f"Attempting to authenticate user with provided API key.")

    try:
        # Fetch all users asynchronously (Keep note of performance concern here)
        stmt = select(User)
        result = await db.execute(stmt)
        users = result.scalars().all()

        matched_user = None
        for user in users:
            # verify_api_key is CPU-bound (sync), no await needed here
            if verify_api_key(plain_api_key, user.hashed_api_key):
                matched_user = user
                break

        if matched_user is None:
            log.warning(f"Authentication failed: No user found for the provided API key.")
            raise credentials_exception

        # We found the user, log success and return the user object
        log.info(f"Successfully authenticated user ID: {matched_user.id}")
        return matched_user # Return the full User object

    except HTTPException as http_exc:
        # Re-raise known HTTP exceptions (like our credentials_exception)
        raise http_exc
    except Exception as e:
        # Catch *other* unexpected database or logic errors during lookup
        log.exception(f"Unexpected error during user lookup for key ending: ...{plain_api_key[-4:]}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Internal server error during authentication."
        ) from e 