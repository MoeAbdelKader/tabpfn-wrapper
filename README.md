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

## Roadmap

See [docs/roadmap.md](docs/roadmap.md) for the development plan.

## Architecture

See [docs/architecture_plan.md](docs/architecture_plan.md) for details on the system design. 