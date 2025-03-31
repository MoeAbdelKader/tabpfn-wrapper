# TabPFN API Wrapper

This project provides a secure and managed RESTful API wrapper around the PriorLabs `tabpfn-client` library. You can access the Cloud UI here https://tabpfnapi.com

## Disclaimer ⚠️

**This is an experimental project and is provided "as-is" without warranty of any kind, express or implied.** Features may change, and stability & security are not guaranteed. Please use it at your own risk and test thoroughly for your use cases.

## Goal

The primary goal is to allow users to interact with the TabPFN API for training (`fit`) and prediction (`predict`) via a RESTful API, allowing agnostic use of TabPFN via any programming language that can make HTTP requests. Users register their TabPFN token once with this service and receive a service-specific API key for subsequent interactions.

## Tech Stack

*   **API Framework:** FastAPI
*   **Database:** PostgreSQL (managed via SQLAlchemy and Alembic)
*   **Containerization:** Docker & Docker Compose
*   **TabPFN Interaction:** `tabpfn-client` library

## Usage Modes

There are three main ways to use the TabPFN API Wrapper:

### 1. Web UI (Cloud Deployment)

*   **Access:** Navigate to [`https://tabpfnapi.com/`](https://tabpfnapi.com/) in your browser.
*   **Purpose:**
    *   Generate your unique API Wrapper Key using your official TabPFN Token.
    *   (If implemented) Access a dashboard to view/manage trained models.
*   **Best for:** Initial setup, generating API keys, potentially visual interaction (if dashboard features exist).

### 2. Cloud API (Programmatic Access)

*   **Base URL:** `https://tabpfnapi.com`
*   **Authentication:**
    1.  Obtain your API Wrapper Key via the Web UI setup process.
    2.  Include the key in the `Authorization: Bearer YOUR_WRAPPER_KEY` header for all API calls (except the initial setup).
*   **Documentation:** Full details on endpoints, request/response formats are available at [`https://tabpfnapi.com/redoc`](https://tabpfnapi.com/redoc).
*   **Example:** See `tests/manual_tests/test_deployed_api.py` for a Python client example.
*   **Best for:** Integrating TabPFN predictions/training into your own applications, scripts, or automated workflows.

### 3. Local Development / Hosting

*   **Purpose:** Running the API service directly on your own machine for development, testing, or local use.
*   **Steps:**
    1.  **Clone the repository:**
        ```bash
        git clone https://github.com/MoeAbdelKader/tabpfn-wrapper.git
        cd tabpfn-wrapper
        ```
    2.  **Set up environment:** Create a Python virtual environment and install dependencies:
        ```bash
        python -m venv venv
        source venv/bin/activate # or venv\Scripts\activate on Windows
        pip install -r requirements.txt
        ```
    3.  **Configure environment variables:** Create a `.env` file in the project root (copy from `.env.example`) or set environment variables for:
        *   `DATABASE_URL` (Connection string for your local/dev database, typically configured via other POSTGRES variables in `.env` for Docker setup)
        *   `SECRET_KEY` (A strong random string for security)
        *   `ALLOWED_ORIGINS` (e.g., `http://localhost:8000` if needed for local UI interaction)
        *   `TABPFN_API_TOKEN` (Your official token, potentially needed for the local setup endpoint)
    4.  **Run the server (using Docker Compose is recommended for local setup, see Getting Started below):**
        ```bash
        # If running without Docker (requires manual DB setup & env vars):
        # uvicorn main:app --reload --port 8000
        ```
    5.  **Access:** If running locally (e.g., via Docker Compose), the API will be available at `http://localhost:8000`, including the docs at `http://localhost:8000/redoc`.
*   **Best for:** Developing new features, testing changes locally before deployment, running in isolated environments.

## Getting Started

These instructions guide you through setting up and running the TabPFN Wrapper API locally using Docker.

### Prerequisites

*   [Docker](https://docs.docker.com/get-docker/) installed
*   [Docker Compose](https://docs.docker.com/compose/install/) installed

### 1. Clone the Repository

```bash
git clone <your-repository-url>
cd tabpfn-wrapper
```

### 2. Configure Environment Variables

Copy the example environment file:

```bash
cp .env.example .env
```

Edit the `.env` file and fill in the necessary details:

*   **Database Credentials:** Set `POSTGRES_USER`, `POSTGRES_PASSWORD`, and `POSTGRES_DB` for your local development database. These values will be used by Docker Compose to initialize the database container.
*   **`SECRET_KEY`:** Generate a strong, unique secret key. You can use the following command:
    ```bash
    openssl rand -base64 32
    ```
    Paste the generated key into the `SECRET_KEY` field in `.env`.

**Important:** The `DATABASE_URL` is constructed automatically from the other `POSTGRES_*` variables in the `.env` file for local development. The `POSTGRES_HOST` should remain `db` as this is the service name defined in `docker-compose.yml`.

### 3. Build and Run with Docker Compose

Build the Docker images and start the API and database containers:

```bash
docker-compose build
docker-compose up -d
```

This command will:
*   Build the `api` service image based on the `Dockerfile`.
*   Build/pull the `postgres` image for the database.
*   Start both containers in detached mode (`-d`).

The API service should now be running and accessible.

### 4. Verify the Service

Check if the API is running by accessing the health endpoint:

```bash
curl http://localhost:8000/health
```

You should receive a response like:

```json
{"status": "ok"}
```

### 5. Next Steps

Now that the service is running locally, refer to the **Usage Guide** below for instructions on how to:
*   Authenticate and get your API key.
*   Train models and make predictions using JSON or CSV uploads.

## Features

- **Authentication**: Securely store and manage TabPFN tokens with API key authentication
- **JSON API**: Train models and get predictions using JSON data
- **CSV Upload**: Upload CSV files directly for training and prediction *(New!)*
- **Secure by Design**: Non-root Docker containers, secret management, and encrypted storage
- **Cloud Ready**: Designed for deployment on Google Cloud Run

## Usage Guide

### Authentication

1. Register your TabPFN token to get an API key:

```bash
curl -X POST \
  -H "Content-Type: application/json" \
  "http://localhost:8000/api/v1/auth/setup" \
  -d '{"tabpfn_token": "your_tabpfn_token_here"}'
```

2. Save the API key from the response:

```json
{
  "api_key": "your_generated_api_key_here"
}
```

3. Use this API key in the `Authorization` header for all subsequent requests:

```
Authorization: Bearer your_generated_api_key_here
```

### Working with CSV Files

#### Training a Model with CSV

```bash
# Replace YOUR_API_KEY with your API key
curl -X POST \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "file=@path/to/your/data.csv" \
  "http://localhost:8000/api/v1/models/fit/upload?target_column=label"
```

The CSV must include a header row. The `target_column` parameter specifies which column contains the target values. All other columns are treated as features.

Response:

```json
{
  "internal_model_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479"
}
```

#### Making Predictions with CSV

```bash
# Replace YOUR_API_KEY and MODEL_ID appropriately
curl -X POST \
  -H "Authorization: Bearer YOUR_API_KEY" \
  -F "file=@path/to/your/prediction_data.csv" \
  "http://localhost:8000/api/v1/models/MODEL_ID/predict/upload?task=classification"
```

The prediction CSV must have the same column structure as the training data (minus the target column).

Response:

```json
{
  "predictions": [0, 1, 0, 1, 0]
}
```

## Deployment

For detailed deployment instructions, see [docs/deployment_guide.md](docs/deployment_guide.md).

## Roadmap

See [docs/roadmap.md](docs/roadmap.md) for the development plan.

## Architecture

See [docs/architecture_plan.md](docs/architecture_plan.md) for details on the system design. 
