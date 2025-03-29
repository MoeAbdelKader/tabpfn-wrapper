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
