# Maintainer Documentation

This document provides guidance for developers maintaining the TabPFN API Wrapper.

## Core Components & Decisions

### Configuration (`tabpfn_api/core/config.py`)

*   **Method:** Uses the `pydantic-settings` library.
*   **Loading:** Loads settings from environment variables (primary) or a `.env` file (for local development).
*   **Key Settings:**
    *   `DATABASE_URL`: PostgreSQL connection string. **HAS NO DEFAULT - MUST BE SET.**
    *   `SECRET_KEY`: Used for encrypting user TabPFN tokens (using Fernet). **HAS NO DEFAULT - MUST BE SET.**
    *   `LOG_LEVEL`: Controls the application's log verbosity (Defaults to INFO).
*   **Local Dev:** Create a `.env` file based on `.env.example`. **DO NOT COMMIT `.env` FILE.**
*   **Production:** Set `DATABASE_URL` and `SECRET_KEY` as environment variables.

### Logging (`tabpfn_api/core/logging_config.py`)

*   **Method:** Uses Python's standard `logging` module.
*   **Setup:** Configured by `setup_logging()` function, called once at the start of `main.py`.
*   **Output:** Logs formatted messages to standard output (console).
*   **Level:** Controlled by the `LOG_LEVEL` setting in `config.py`.

### Database (PostgreSQL + SQLAlchemy + Alembic)

*   **Choice:** PostgreSQL was chosen over SQLite for better concurrency handling, even at moderate scale, aligning better with typical web application needs.
*   **Interaction:** SQLAlchemy is used as the ORM/toolkit.
    *   Models are defined in `tabpfn_api/models/`.
    *   Database session management will be handled in `tabpfn_api/db/database.py`.
*   **Migrations:** Alembic is used for managing database schema changes.
    *   Initialize Alembic if not already done: `alembic init alembic`
    *   Generate migrations: `alembic revision --autogenerate -m "Description of changes"`
    *   Apply migrations: `alembic upgrade head`
    *   Alembic configuration is in `alembic.ini`.

### Authentication Flow (API Keys)

*   Users provide their TabPFN token via `/auth/setup`.
*   The service verifies the token.
*   A unique, secure API key is generated for *our* service (`secrets.token_urlsafe`).
*   The *hash* of this API key is stored in the DB (`passlib.hash.bcrypt`).
*   The user's TabPFN token is *encrypted* using the `SECRET_KEY` (`cryptography.fernet`) and stored in the DB, associated with the user.
*   Subsequent requests use `Authorization: Bearer <our_api_key>`.
*   A FastAPI dependency verifies the bearer token against the stored hashes and retrieves/decrypts the associated TabPFN token for use.

## Running Locally

1.  Ensure Docker and Docker Compose are installed.
2.  Create a `.env` file from `.env.example` and set a secure `SECRET_KEY` and the correct `DATABASE_URL` (refer to the comment in `.env.example` for the typical local Docker value).
3.  Run `docker compose up --build`.
4.  The API will be available at `http://localhost:8000`.
5.  To run database migrations (after Alembic is set up):
    *   `docker compose exec api alembic revision --autogenerate -m "Migration description"`
    *   `docker compose exec api alembic upgrade head`

## Project Structure

*   `main.py`: FastAPI application entry point.
*   `requirements.txt`: Python dependencies.
*   `Dockerfile`: Defines the application container.
*   `docker-compose.yml`: Defines local development services (API, DB).
*   `.env.example`: Example environment variables.
*   `tabpfn_api/`: Main application package.
    *   `core/`: Core logic (config, logging, security utilities).
    *   `api/`: FastAPI routers and endpoints.
    *   `db/`: Database connection and session management.
    *   `models/`: SQLAlchemy database models.
    *   `services/`: Business logic layer.
    *   `schemas/`: Pydantic models for API request/response validation.
    *   `tabpfn_interface/`: Wrapper around the `tabpfn-client` library.
*   `tests/`: Unit and integration tests.
*   `docs/`: Project documentation (Roadmap, Architecture, Maintainer Docs, etc.).
*   `alembic/`: Database migration scripts (once initialized).
*   `alembic.ini`: Alembic configuration file (once initialized).

*(Add more sections as needed, e.g., Testing Strategy, Deployment Details)*

## Core Architecture

Refer to `docs/architecture_plan.md` for the overall system design (FastAPI layers, database, etc.).

## Authentication Flow (`/auth/setup`)

The primary goal of Milestone 2 was to implement user registration and API key generation.

1.  **Request:** The user sends a `POST` request to `/api/v1/auth/setup` with their existing TabPFN API token in the JSON body.
2.  **API Layer (`api/auth.py`):** The `register_user` endpoint receives the request, validates the body using `UserSetupRequest` schema, and retrieves a database session using the `get_db` dependency.
3.  **Service Layer (`services/auth_service.py`):** The endpoint calls `setup_user`.
4.  **Token Verification (`tabpfn_interface/client.py`):**
    *   `setup_user` first calls `verify_tabpfn_token`.
    *   `verify_tabpfn_token` uses the `tabpfn_client` library (`from tabpfn_client.client import ServiceClient`) to make a real API call (`ServiceClient.get_api_usage(access_token=token)`) to the external TabPFN service.
    *   **Error Handling Note:** The `tabpfn-client` library (as of v0.1.7) does not seem to expose specific exceptions like `UsageLimitReached` or `ConnectionError` for direct import. Therefore, `verify_tabpfn_token` catches the generic `Exception` and inspects the error message content (using keywords like "usage limit", "connection error", "authentication failed") to determine if the token is valid, if a usage limit was hit (still considered valid for verification), or if a connection/authentication error occurred.
    *   It returns `True` if the `get_api_usage` call succeeds OR if a usage limit error is detected. It returns `False` for authentication errors, connection errors, or other unexpected exceptions.
5.  **Key Generation & Storage (`services/auth_service.py` & `core/security.py`):**
    *   If `verify_tabpfn_token` returns `True`, `setup_user` proceeds.
    *   It generates a unique, secure API key for *our* service using `secrets.token_urlsafe()` (`security.generate_api_key`).
    *   It hashes this service key using `passlib` (bcrypt) (`security.get_api_key_hash`).
    *   It encrypts the user's original TabPFN token using `cryptography.fernet` (`security.encrypt_token`). The Fernet key is derived from the `SECRET_KEY` environment variable (see `core/config.py`).
    *   It creates a new `User` record (defined in `models/user.py`) containing the `hashed_api_key` and `encrypted_tabpfn_token`.
    *   It saves this record to the PostgreSQL database.
6.  **Response (`services/auth_service.py` -> `api/auth.py`):**
    *   `setup_user` returns the *plain text* generated service API key.
    *   The API endpoint wraps this in the `UserSetupResponse` schema and returns a `201 Created` status.

## Debugging `tabpfn-client` Import Issues (Historical)

During development, significant time was spent diagnosing why `from tabpfn import ServiceClient` failed with `ModuleNotFoundError: No module named 'tabpfn'`, despite `pip list` showing `tabpfn-client` was installed in the Docker container.

**Key Findings:**
*   The `pip install tabpfn-client` command was completing the metadata registration but **failed silently** to create the actual importable `tabpfn` directory in `site-packages`, even on the full `python:3.11` base image. The reason for this silent failure is likely within the package's `setup.py` or build process.
*   The correct way to import is from the `tabpfn_client` namespace, specifically `from tabpfn_client.client import ServiceClient`, as confirmed by the library's README and API documentation.
*   Specific exception classes (`UsageLimitReached`, `ConnectionError`) were not found during import attempts from likely locations (`tabpfn_client`, `tabpfn_client.client`, `tabpfn_client.tabpfn_common_utils`).

**Resolution:**
*   Imports were corrected to use `from tabpfn_client.client import ServiceClient`.
*   Error handling in `verify_tabpfn_token` was changed to catch generic `Exception` and inspect the message.

If similar import issues arise with this or other libraries:
1.  Verify the exact import path used vs. the library's documentation/examples.
2.  Check `pip list` inside the running container.
3.  Check the contents of the relevant directory in `site-packages` inside the container (`ls -lA /usr/local/lib/python3.11/site-packages/<library_name>/`). Ensure expected files (`__init__.py`, module files) exist.
4.  Consider using the full Python base image (`python:X.Y`) instead of `slim` if silent installation failures are suspected.

## Environment Variables

Ensure the following environment variables are set (e.g., in `.env` for local Docker Compose):
*   `DATABASE_URL`: PostgreSQL connection string (e.g., `postgresql://user:password@db:5432/tabpfndb`).
*   `SECRET_KEY`: A 32-byte (64 hex chars) random key for encryption (generate using `openssl rand -hex 32`). **CRITICAL for security.**

## Future Authentication Steps (Milestone 2 - Incomplete)

*   An authentication dependency (`get_current_user_tabpfn_token` in `core/security.py`) needs to be implemented. This will extract the `Bearer <service_api_key>` from requests, verify the key hash against the database, decrypt the stored TabPFN token, and make the TabPFN token available to protected endpoints.
*   Integration tests need to be added for `/auth/setup` and the future authentication dependency.
