import logging
from sqlalchemy.orm import Session
from sqlalchemy.ext.asyncio import AsyncSession

from tabpfn_api.models.user import User
from tabpfn_api.core.security import (
    generate_api_key,
    get_api_key_hash,
    encrypt_token,
)
from tabpfn_api.tabpfn_interface.client import verify_tabpfn_token

log = logging.getLogger(__name__)


class AuthServiceError(Exception):
    """Custom exception for authentication service errors."""
    pass


class InvalidTabPFNTokenError(AuthServiceError):
    """Raised when the provided TabPFN token is invalid."""
    pass


async def setup_user(db: AsyncSession, tabpfn_token: str) -> str:
    """Sets up a new user by verifying their TabPFN token and generating a service API key.

    Args:
        db: The async database session.
        tabpfn_token: The user's TabPFN token.

    Returns:
        The newly generated plain-text service API key for the user.

    Raises:
        InvalidTabPFNTokenError: If the provided TabPFN token is not valid.
        AuthServiceError: For other errors during the setup process.
    """
    log.info("Attempting to set up a new user.")

    # 1. Verify the TabPFN token
    is_valid = verify_tabpfn_token(token=tabpfn_token)
    if not is_valid:
        log.warning("User setup failed: Invalid TabPFN token provided.")
        raise InvalidTabPFNTokenError("The provided TabPFN token could not be verified.")

    log.debug("TabPFN token verified successfully.")

    try:
        # 2. Generate a new service API key
        plain_api_key = generate_api_key()
        log.debug(f"Generated new service API key.")

        # 3. Hash the service API key
        hashed_key = get_api_key_hash(plain_api_key)
        log.debug(f"Hashed service API key.")

        # 4. Encrypt the TabPFN token
        encrypted_token = encrypt_token(tabpfn_token)
        log.debug(f"Encrypted TabPFN token.")

        # 5. Create and store the user record
        db_user = User(
            hashed_api_key=hashed_key,
            encrypted_tabpfn_token=encrypted_token
        )
        db.add(db_user)
        await db.commit()
        await db.refresh(db_user)
        log.info(f"Successfully created and stored new user record with ID: {db_user.id}")

        # 6. Return the plain text service API key
        return plain_api_key

    except Exception as e:
        log.exception(f"An error occurred during user setup: {e}")
        await db.rollback() # Ensure transaction is rolled back on error
        raise AuthServiceError("An internal error occurred during user setup.") from e 