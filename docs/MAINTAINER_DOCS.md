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

## Interacting with `tabpfn-client` Library

This section details key findings and patterns for using the external `tabpfn-client` library.

### Authentication for API Calls

*   **Singleton Client:** The core `ServiceClient` (in `tabpfn_client.client`) is implemented as a Singleton. Methods like `fit`, `predict`, `get_api_usage` are `@classmethod`s.
*   **Setting the Token:** Authentication is managed globally for the singleton instance. Before making calls that require authentication (like `fit` or `predict`), the user's access token must be set using the standalone function `tabpfn_client.set_access_token(token)`. This function updates the default headers used by the `ServiceClient`'s internal `httpx` client.
*   **Calling Methods:** Once the token is set via `set_access_token`, classmethods like `ServiceClient.fit(...)` can be called directly. They will implicitly use the token set on the shared client instance.
*   **Token Verification:** The `ServiceClient.get_api_usage(access_token=...)` method *does* accept the token directly as an argument and can be used for verifying a token without setting it globally.
*   **Concurrency Note:** Using a globally set token for a singleton client in a concurrent server environment (like FastAPI) *could* potentially lead to race conditions if not handled carefully internally by the `tabpfn-client` library (e.g., using thread-local storage). This hasn't been explicitly verified and should be monitored.

### Method-Specific Arguments (`fit`)

*   **`ServiceClient.fit(X, y, config=None)`:**
    *   Does **not** accept an `access_token` argument directly.
    *   The `config` dictionary is optional according to docs, but internal code seems to require the `paper_version` key.
    *   Our wrapper (`fit_model` in `tabpfn_interface/client.py`) ensures `config` passed to `ServiceClient.fit` always contains `paper_version` (defaulting to `False`) and filters out any other keys not explicitly mentioned in the `fit` documentation (like prediction parameters).

### Error Handling

*   The library does not seem to export specific exception classes for common errors (e.g., `AuthenticationError`, `UsageLimitError`).
*   Our interface layer (`tabpfn_interface/client.py`) catches generic `Exception` during client interactions.
*   For `verify_tabpfn_token`, we inspect the exception message string to heuristically determine the cause (invalid token, usage limit, connection error).
*   For `fit_model`, we catch generic exceptions and wrap them in `TabPFNInterfaceError`, passing the original error message up.

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
    *   `verify_tabpfn_token` uses `ServiceClient.get_api_usage(access_token=token)` (see *Interacting with `tabpfn-client` Library* section above for details on error handling).
    *   It returns `True` if the call succeeds or a usage limit error is detected.
5.  **Key Generation & Storage (`services/auth_service.py` & `core/security.py`):**
    *   If verification is successful, `setup_user` proceeds.
    *   It generates a unique service API key (`security.generate_api_key`).
    *   It hashes this service key (`security.get_api_key_hash`).
    *   It encrypts the user's original TabPFN token (`security.encrypt_token`).
    *   It creates and saves a `User` record.
6.  **Response (`services/auth_service.py` -> `api/auth.py`):**
    *   Returns the plain text service API key.

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
