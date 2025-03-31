 # TabPFN API Wrapper - Development Roadmap

**Goal:** Deliver a functional and reliable TabPFN API wrapper incrementally. This is a checklist for implementation.

---

### Milestone 1: Project Setup & Foundation

*   [x] Initialize Git repository.
*   [x] Set up project directory structure (`tabpfn_api`, `tests`, `docs`).
*   [x] Set up Python virtual environment (`venv`).
*   [x] Add initial dependencies (`fastapi`, `uvicorn`, `sqlalchemy`, `psycopg2-binary`, `pydantic`, `python-dotenv`, `cryptography`, `passlib`, `tabpfn-client`, `alembic`) to `requirements.txt`.
*   [x] Create a basic FastAPI application instance (`main.py`) with a simple root endpoint (`/`) and a health check endpoint (`/health`).
*   [x] Create initial `Dockerfile` to containerize the basic application.
*   [x] Create `docker-compose.yml` for local development (API + PostgreSQL).
*   [x] Verify the basic app runs locally using `docker-compose up`.
*   [x] Set up configuration loading using Pydantic `BaseSettings` from `.env` file/environment variables (`tabpfn_api/core/config.py`).
*   [x] Set up basic logging configuration.

---

### Milestone 2: Core Authentication

*   **Goal:** Allow users to securely register their TabPFN token and get an API key for our service.
*   [x] Define Database Models (`tabpfn_api/models/user.py`): Create `User` model (stores user ID, hashed API key, encrypted TabPFN token, timestamp).
*   [x] Set up Database Connection (`tabpfn_api/db/database.py`): Configure SQLAlchemy engine and session handling for PostgreSQL (Note: used PostgreSQL, not SQLite as originally written).
*   [x] Initialize Database Schema: Add logic to create tables (`metadata.create_all()`) on startup or via a simple script.
*   [x] Implement TabPFN Interface Function (`tabpfn_api/tabpfn_interface/client.py`): Create a function `verify_tabpfn_token(token: str) -> bool` that uses `tabpfn-client` (e.g., attempts `get_api_usage`) to check if a token is valid. Handle exceptions from `tabpfn-client`.
*   [x] Implement Authentication Service Logic (`tabpfn_api/services/auth_service.py`):
    *   Function `setup_user(tabpfn_token: str) -> str`: Verifies token using interface, generates a unique API key (e.g., JWT or random string), hashes the API key, encrypts the TabPFN token, stores the mapping in the database, returns the *raw* API key.
*   [x] Implement API Endpoint (`tabpfn_api/api/auth.py`):
    *   `POST /auth/setup`: Takes `tabpfn_token` in request body, calls `auth_service.setup_user`, returns the generated API key. Use Pydantic for request body validation.
*   [x] Implement Authentication Middleware/Dependency (`tabpfn_api/core/security.py`):
    *   Create a FastAPI dependency (`get_current_user_token`) that:
        *   Extracts the bearer token (our API key) from the `Authorization` header.
        *   Looks up the hashed API key in the database.
        *   If found, retrieves and decrypts the associated TabPFN token.
        *   Returns the TabPFN token.
        *   Raises `HTTPException` (401 Unauthorized) if token is missing, invalid, or not found.
*   [x] Add basic integration tests for the `/auth/setup` endpoint and the authentication dependency.

---

### Milestone 3: Core Modeling - `fit` Endpoint

*   **Goal:** Allow authenticated users to train a TabPFN model.
*   [x] Define Database Model (`tabpfn_api/models/model.py`): Create `ModelMetadata` model (stores our internal `model_id`, the `train_set_uid` from TabPFN, `user_id` foreign key, timestamp, basic metadata like feature count/sample count).
*   [x] Implement TabPFN Interface Function (`tabpfn_api/tabpfn_interface/client.py`):
    *   Function `fit_model(tabpfn_token: str, features: list, target: list, config: dict) -> str`:
        *   Converts input lists/dicts to NumPy arrays expected by `tabpfn-client`.
        *   Calls `ServiceClient.fit(X, y, **config)` using the provided `tabpfn_token`.
        *   Returns the `train_set_uid` from TabPFN.
        *   Handles data conversion errors and `tabpfn-client` exceptions.
*   [x] Implement Model Service Logic (`tabpfn_api/services/model_service.py`):
    *   Function `train_new_model(user_tabpfn_token: str, features: list, target: list, config: dict) -> str`:
        *   Calls the `tabpfn_interface.fit_model`.
        *   Generates a unique internal `model_id` (e.g., `uuid4`).
        *   Retrieves user ID based on the token (may need adjustment to auth dependency or service structure).
        *   Saves the mapping (`model_id`, `train_set_uid`, `user_id`, timestamp, metadata) to the `ModelMetadata` table.
        *   Returns the internal `model_id`.
*   [x] Implement API Endpoint (`tabpfn_api/api/models.py`):
    *   `POST /models/fit`:
        *   Requires authentication (use the dependency from Milestone 2).
        *   Takes features (as a list of lists, where each inner list is a data row), target (as a list), and optional config dictionary in the JSON request body (define Pydantic model).
        *   Calls `model_service.train_new_model` with the authenticated user's TabPFN token.
        *   Returns the generated internal `model_id`.
*   [x] Add integration tests for the `/models/fit` endpoint, ensuring authentication is required and data is processed correctly (mocking the TabPFN call might be necessary for speed/reliability in tests).

---

### Milestone 4: Core Modeling - `predict` Endpoint

*   **Goal:** Allow authenticated users to get predictions using a previously trained model.
*   [x] Implement TabPFN Interface Function (`tabpfn_api/tabpfn_interface/client.py`):
    *   Function `predict_model(tabpfn_token: str, train_set_uid: str, features: list, task: str, output_type: str, config: dict) -> list`:
        *   Converts input lists/dicts to NumPy arrays.
        *   Calls `ServiceClient.predict(train_set_uid, x_test, task=task, output_type=output_type, **config)` using the provided `tabpfn_token`.
        *   Converts the NumPy result back to standard Python lists.
        *   Returns the predictions/probabilities.
        *   Handles data conversion errors and `tabpfn-client` exceptions.
*   [x] Implement Model Service Logic (`tabpfn_api/services/model_service.py`):
    *   Function `get_predictions(user_tabpfn_token: str, internal_model_id: str, features: list, task: str, output_type: str, config: dict) -> list`:
        *   Look up the `ModelMetadata` in the database using `internal_model_id`.
        *   Verify the requesting user owns this model (check `user_id`). Raise `HTTPException` (403 Forbidden) if not owner.
        *   Retrieve the `train_set_uid`.
        *   Call `tabpfn_interface.predict_model` with the user's token, `train_set_uid`, and other parameters.
        *   Return the results.
*   [x] Implement API Endpoint (`tabpfn_api/api/models.py`):
    *   `POST /models/{model_id}/predict`: (Use `model_id` as path parameter).
        *   Requires authentication.
        *   Takes features, task, output_type, and optional config in request body (define Pydantic model).
        *   Calls `model_service.get_predictions` with the authenticated user's TabPFN token and `model_id`.
        *   Returns the predictions.
*   [x] Add integration tests for the `/models/{model_id}/predict` endpoint, checking authentication, ownership, and data processing.

---

### Milestone 5: Basic Usability & Reliability

*   **Goal:** Make the API minimally usable and robust.
*   [x] Refine Logging: Ensure important events (model fit start/end, prediction start/end, errors) are logged with relevant context (e.g., `model_id`).
*   [x] Refine Error Handling: Ensure `tabpfn-client` errors are caught and translated into user-friendly HTTP error responses (e.g., 400 Bad Request for invalid data, 503 Service Unavailable if TabPFN service fails).
*   [x] Improve API Documentation: Review and refine the auto-generated OpenAPI docs (via FastAPI). Add descriptions, examples to Pydantic models and endpoint definitions.
*   [x] Implement `GET /models/available` Endpoint:
    *   Add function to `tabpfn_interface` to call `TabPFNClassifier.list_available_models()` / `TabPFNRegressor.list_available_models()`.
    *   Add simple service function.
    *   Add API endpoint (does not require authentication).
*   [x] Implement `GET /models` Endpoint:
    *   Add service function to list `ModelMetadata` records associated with the authenticated user from the database.
    *   Add API endpoint requiring authentication.

---

### Milestone 6: Initial Deployment

*   **Goal:** Get the working API deployed and accessible.
*   [ ] Choose Deployment Target: Decide between Simple VM or Cloud Run (or similar).
*   [ ] Configure Environment Variables: Set up production environment variables (Database URL, API secrets, etc.) securely in the chosen deployment environment.
*   [ ] Build Production Docker Image: Ensure Dockerfile is optimized for production (e.g., not installing dev dependencies).
*   [ ] Push Image to Registry (if needed, e.g., for Cloud Run, ECR, Docker Hub).
*   [ ] Deploy Container: Deploy using Docker Compose on VM or via Cloud Run/App Runner console/CLI.
*   [ ] Test Deployed API: Perform basic sanity checks on the deployed endpoints.
*   [ ] Set up Basic Monitoring: Use built-in Cloud Run monitoring or a simple uptime checker for VM.

---

### Milestone 7: Further Enhancements (Future)

*   [ ] Implement `DELETE /models/{model_id}` Endpoint.
*   [ ] Add the ability for users to delete their account
*   [ ] Implement `GET /usage` Endpoint (requires calling `ServiceClient.get_api_usage`).
*   [ ] Add more comprehensive testing (unit tests for services, edge cases).
*   [ ] Implement Input Validation (e.g., check feature count matches expected for prediction).
*   [ ] Consider database migrations if schema evolves (using Alembic).
*   [ ] Investigate caching for `predict` calls if performance becomes an issue.
*   [ ] Investigate asynchronous task handling for long `fit`/`predict` calls if needed.
*   [ ] Optimize db queries for get_current_user_token. (We currently retrieve all records from the db and loop through them)
*   [  ] Add ability for users to upload CSV files
