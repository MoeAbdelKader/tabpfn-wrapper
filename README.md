# TabPFN API Wrapper

This project provides a secure and managed RESTful API wrapper around the PriorLabs `tabpfn-client` library.

## Goal

The primary goal is to allow users to interact with the TabPFN API for training (`fit`) and prediction (`predict`) via a RESTful API, allowing agnostic use of TabPFN via any programming language that can make HTTP requests. Users register their TabPFN token once with this service and receive a service-specific API key for subsequent interactions.

## Tech Stack

*   **API Framework:** FastAPI
*   **Database:** PostgreSQL (managed via SQLAlchemy and Alembic)
*   **Containerization:** Docker & Docker Compose
*   **TabPFN Interaction:** `tabpfn-client` library

## Getting Started

*(Instructions will be added here once the basic setup is complete)*

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