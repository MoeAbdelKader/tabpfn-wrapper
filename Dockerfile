# Stage 1: Builder Stage - Install dependencies
FROM python:3.11 as builder

# Set working directory
WORKDIR /app

# Set environment variables to prevent pyc files and ensure logs are sent directly
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1

# Install build dependencies if needed (kept commented as psycopg2-binary usually suffices)
# RUN apt-get update && apt-get install -y --no-install-recommends build-essential libpq-dev && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN pip install --no-cache-dir --upgrade pip

# Create a virtual environment
RUN python -m venv /opt/venv

# Activate virtual environment for subsequent commands
ENV PATH="/opt/venv/bin:$PATH"

# Copy only requirements.txt first to leverage Docker cache
COPY requirements.txt .

# Install production dependencies into the virtual environment
RUN pip install --no-cache-dir -r requirements.txt

# Stage 2: Runtime Stage - Create the final image
FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE 1
ENV PYTHONUNBUFFERED 1
# Add venv to path
ENV PATH="/opt/venv/bin:$PATH"

# Create a non-root user and group
RUN groupadd -r appuser && useradd --no-log-init -r -g appuser appuser

# Copy the virtual environment from the builder stage
COPY --from=builder /opt/venv /opt/venv

# Copy only the necessary application code from the current directory
# Use --chown to set the owner to the non-root user
COPY --chown=appuser:appuser tabpfn_api ./tabpfn_api
COPY --chown=appuser:appuser main.py .

# Ensure the app directory is owned by the appuser
# RUN chown -R appuser:appuser /app # This might be redundant due to --chown but can be added for safety

# Switch to the non-root user
USER appuser

# Expose the port the app runs on (Cloud Run uses this hint but manages the actual port)
EXPOSE 8000

# Command to run the application using Uvicorn
# Use 0.0.0.0 to make it accessible from outside the container
# The port is set by Cloud Run via the PORT env var, but Uvicorn needs it specified.
# Cloud Run injects PORT=8080 by default, so we use that if present, otherwise default to 8000.
# We use sh -c to allow environment variable expansion in the command.
CMD exec uvicorn main:app --host 0.0.0.0 --port ${PORT:-8000} --workers 1
# Using exec ensures Uvicorn receives signals correctly for graceful shutdown.
# Cloud Run performs best with a single worker (--workers 1) as it handles scaling by launching more instances. 