# TabPFN API Wrapper - Architecture Plan

**Version:** 1.0

## 1. Overview & Goals

This document outlines the technical architecture for building a REST API wrapper around the `PriorLabs/tabpfn-client` Python library.

**Primary Goals:**

*   Provide a stable, simple RESTful interface to TabPFN's core `fit` and `predict` functionalities.
*   Enable usage of TabPFN from various programming languages via standard HTTP requests.
*   Ensure a secure way for users to leverage their existing TabPFN credentials (tokens).
*   Keep the architecture simple, reliable, and maintainable for a small team.
*   Deploy using Docker for environment consistency.

**Guiding Principles:**

*   **Simplicity First:** Avoid premature optimization or unnecessary complexity.
*   **Reliability:** Ensure the wrapper handles basic errors gracefully.
*   **Maintainability:** Write clean, well-structured code with clear separation of concerns.
*   **Standard Practices:** Use common, well-understood tools and patterns.

## 2. Technology Stack

*   **Programming Language:** Python 3.10+
*   **Web Framework:** FastAPI (for performance, async support, auto-docs, data validation)
*   **Data Validation:** Pydantic (integrated with FastAPI)
*   **Configuration:** Pydantic Settings (loads from env vars/.env)
*   **Database:** PostgreSQL
*   **ORM/DB Toolkit:** SQLAlchemy (Core/ORM features)
*   **Migrations:** Alembic (for managing database schema changes)
*   **Containerization:** Docker & Docker Compose (for development and deployment)
*   **Authentication:** Custom API Key (hashed via `passlib`) + Encrypted TabPFN Token (`cryptography`)
*   **TabPFN Interaction:** `tabpfn-client` Python library.
*   **Logging:** Standard Python `logging` module.

## 3. System Architecture

We will use a standard 3-layer architecture within the FastAPI application, packaged in a Docker container.
```markdown
+-------------------------------- Docker Container ---------------------------------+
| |
| +-----------------+ +-------------------+ +-------------------------+ |
| | API Layer |<---->| Service Layer |<---->| TabPFN Interface Layer | |
| | (FastAPI Routes)| | (Business Logic) | | (Wraps tabpfn-client) | |
| +-------^---------+ +---------^---------+ +------------^------------+ |
| | | | |
| | | | |
| +-------v---------+ +---------v---------+ +------------v------------+ |
| | Auth Middleware | | Database | | tabpfn-client Lib |-----> [TabPFN Server]
| | (API Key Check) | | (PostgreSQL via SQLAlchemy)| | | |
| +-----------------+ +-------------------+ +-------------------------+ |
| |
+-----------------------------------------------------------------------------------+
```

### 3.1. API Layer (FastAPI Routers)

*   **Location:** `tabpfn_api/api/`
*   **Responsibility:**
    *   Define HTTP endpoints (routes) using FastAPI routers (`/auth`, `/models`).
    *   Handle incoming HTTP requests and parse request bodies.
    *   Use Pydantic models for automatic request validation and response serialization.
    *   Call appropriate functions in the Service Layer.
    *   Return HTTP responses (data or errors).
    *   Handle API-level exceptions and map them to appropriate HTTP status codes.
*   **Implementation:** Use FastAPI's `APIRouter`, Pydantic models for request/response bodies, dependency injection for services and authentication.

### 3.2. Service Layer (Business Logic)

*   **Location:** `tabpfn_api/services/`
*   **Responsibility:**
    *   Contain the core business logic of the application.
    *   Orchestrate calls between the API layer, Database, and TabPFN Interface Layer.
    *   Implement the logic for user setup (storing TabPFN token mapping), model training, prediction, etc.
    *   Perform any necessary data transformations not handled by the TabPFN Interface.
    *   Contain logic for validating user permissions/ownership if needed (e.g., ensuring a user can only access their trained models).
*   **Implementation:** Plain Python functions/classes. Should be framework-agnostic where possible.

### 3.3. TabPFN Interface Layer

*   **Location:** `tabpfn_api/tabpfn_interface/`
*   **Responsibility:**
    *   Act as a dedicated wrapper around the `tabpfn-client` library.
    *   Expose simplified methods for core actions (`fit`, `predict`, `check_token`, `get_usage`, etc.).
    *   Handle the direct interaction with `tabpfn-client`, including passing the user's proxied TabPFN token.
    *   Convert data formats between what the Service Layer uses (e.g., standard Python lists/dicts) and what `tabpfn-client` expects (e.g., NumPy arrays).
    *   Catch exceptions specific to `tabpfn-client` and translate them into application-specific exceptions if needed.
*   **Implementation:** Python class or module wrapping `tabpfn_client.ServiceClient` and potentially `TabPFNClassifier`/`TabPFNRegressor`. Include utility functions for data conversion.

### 3.4. Database (PostgreSQL / SQLAlchemy / Alembic)

*   **Location:** `tabpfn_api/db/`, `tabpfn_api/models/`
*   **Responsibility:**
    *   Persist mapping between our generated API keys and the user's provided TabPFN token.
    *   Store metadata about trained models (e.g., our internal `model_id`, the corresponding `train_set_uid` from TabPFN, user association, timestamp).
*   **Implementation:**
    *   Use SQLAlchemy ORM features.
    *   Define models (e.g., `User`, `ModelMetadata`) using SQLAlchemy's Declarative Base in `tabpfn_api/models/`.
    *   Use PostgreSQL database, managed via Docker Compose for local development.
    *   Use Alembic for managing database schema migrations. Initialize with `alembic init alembic` and store migrations in the `alembic/versions/` directory.
    *   Database connection managed via `tabpfn_api/db/database.py` using URL from `config.py`.

### 3.5. Authentication (Token Proxy Model)

*   **Flow:**
    1.  **Setup:** User provides their *existing* TabPFN token via a secure setup endpoint (`POST /auth/setup`).
    2.  **Verification:** The Service Layer uses the TabPFN Interface to verify the provided token is valid (e.g., calling a function like `is_auth_token_outdated` or `get_api_usage` which requires a valid token).
    3.  **API Key Generation:** If the token is valid, generate a secure, unique API key (e.g., using `secrets.token_urlsafe()`) for *our* API.
    4.  **Storage:** Store the mapping: `hashed_api_key -> user_id`, `user_id -> encrypted_tabpfn_token` securely in the database. **Important:** Store a hash of our API key (using `passlib` with bcrypt), not the raw key. The TabPFN token must be stored encrypted at rest (using `cryptography.fernet`).
    5.  **Usage:** User includes `our_api_key` in the `Authorization: Bearer <our_api_key>` header for subsequent requests.
    6.  **Middleware/Dependency:** A FastAPI dependency (`Depends`) intercepts requests, extracts `our_api_key` from the `Authorization: Bearer <our_api_key>` header, looks up the hash in the database, retrieves the corresponding `user_id`, and fetches/decrypts the `tabpfn_token` for that user. Makes the token available.
    7.  **TabPFN Calls:** The Service Layer passes the retrieved `tabpfn_token` to the TabPFN Interface Layer for actual calls to the TabPFN service.
*   **Implementation:** Use FastAPI dependencies, `passlib[bcrypt]` for hashing, `cryptography` for Fernet encryption, `secrets` module for key generation.

## 4. Deployment Strategy (Docker)

*   **Packaging:** The entire application, including Python, dependencies, and code, will be packaged into a single Docker image using a `Dockerfile`.
*   **Development:** Use `docker-compose.yml` for easy local development environment setup, including mounting code for hot-reloading and mounting a volume for the PostgreSQL database.
*   **Production Deployment Targets (Choose one simple option):**
    1.  **Single VM (e.g., AWS EC2, Google Compute Engine, DigitalOcean Droplet):**
        *   Install Docker and Docker Compose on the VM.
        *   Pull the image and run using `docker-compose up -d`.
        *   Requires manual VM setup and basic maintenance (OS updates, Docker updates).
        *   **Pro:** Full control, straightforward. **Con:** Requires VM management.
    2.  **Managed Container Service (e.g., Google Cloud Run, AWS App Runner):**
        *   Build the Docker image and push it to a container registry (e.g., Docker Hub, Google Artifact Registry, AWS ECR).
        *   Configure the service (Cloud Run, App Runner) to pull and run the image.
        *   Handles scaling (even to zero), HTTPS termination, and basic infrastructure management.
        *   **Pro:** Simplest operational overhead, pay-for-use. **Con:** Platform limits (check if suitable for TabPFN's potential resource needs), less control than VM.
*   **Recommendation:** Start with **Google Cloud Run** if comfortable with cloud services, as it balances simplicity and power. Otherwise, a **Single VM** with Docker Compose is a very solid and understandable starting point.

## 5. Configuration Management

*   Use environment variables for all configuration (database URL, API secrets, logging level, etc.).
*   Use `pydantic-settings` library (`tabpfn_api/core/config.py`) to load and validate configuration from environment variables and/or `.env` files.

## 6. Logging & Error Handling

*   **Logging:** Use Python's standard `logging` module configured via `tabpfn_api/core/logging_config.py`, reading the log level from configuration (`config.py`). Logs to console by default.
*   **Error Handling:**
    *   Use FastAPI's exception handling mechanisms (`@app.exception_handler`).
    *   Define custom exception classes (`TabPFNClientError`, `AuthenticationError`, `ValidationError`) in `tabpfn_api/core/exceptions.py`.
    *   Return standardized JSON error responses (e.g., `{"detail": "Error message"}`).

## 7. Testing

*   Use `pytest`.
*   Focus initially on **integration tests** that test API endpoints through the service layer (potentially mocking the actual TabPFN calls initially or using small, real calls if feasible).
*   Use FastAPI's `TestClient`.

## 8. Conclusion

This architecture prioritizes a simple, standard approach using FastAPI and Docker. It provides a clear separation of concerns, enabling the team to build and maintain the API wrapper effectively. We will start with the core features and iterate, keeping complexity low.