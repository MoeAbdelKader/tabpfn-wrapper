# TabPFN Wrapper API - Deployment & Testing Guide

This document outlines the process for building, deploying, and testing the TabPFN Wrapper API on Google Cloud Platform.

## Prerequisites

- [Google Cloud SDK](https://cloud.google.com/sdk/docs/install) installed and configured
- Docker installed (for local building)
- Access to a GCP project with the following services enabled:
  - Cloud Run
  - Secret Manager
  - Artifact Registry
- Python 3.7+ (for running tests)

## Environment Configuration

Create the following secrets in Secret Manager:

- `tabpfn-db-url`: PostgreSQL connection string for the database
- `tabpfn-secret-key`: Secure random string for encryption

## Building for Production

### Building on macOS with Apple Silicon (M1/M2)

When building on Apple Silicon for deployment to Google Cloud (x86_64), you must specify the target platform:

```bash
# Set your configuration variables
export PROJECT_ID=your-project-id
export REGION=your-region
export REPOSITORY=your-artifact-repository
export IMAGE_NAME=your-image-name

# Build for the linux/amd64 platform
docker buildx build --platform linux/amd64 \
  -t $REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/$IMAGE_NAME:latest .

# Authenticate Docker with GCP
gcloud auth configure-docker $REGION-docker.pkg.dev

# Push the image
docker push $REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/$IMAGE_NAME:latest
```

If you encounter slow builds, consider using Cloud Build instead:

```bash
gcloud builds submit --tag $REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/$IMAGE_NAME:latest
```

## Deployment to Cloud Run

```bash
# Deploy to Cloud Run
gcloud run deploy SERVICE_NAME \
  --image $REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/$IMAGE_NAME:latest \
  --platform managed \
  --region $REGION \
  --memory 1Gi \
  --timeout 300s \
  --update-secrets=DATABASE_URL=tabpfn-db-url:latest,SECRET_KEY=tabpfn-secret-key:latest
```

### Required Permissions

Ensure the Cloud Run service account has:
- `roles/secretmanager.secretAccessor` (for accessing secrets)

You can add this with:

```bash
gcloud projects add-iam-policy-binding $PROJECT_ID \
  --member="serviceAccount:PROJECT_NUMBER-compute@developer.gserviceaccount.com" \
  --role="roles/secretmanager.secretAccessor"
```

## Testing the Deployed API

### Manual Testing with Curl

```bash
# Get your service URL
SERVICE_URL=$(gcloud run services describe SERVICE_NAME --platform managed --region $REGION --format 'value(status.url)')

# Test health endpoint
curl $SERVICE_URL/health

# Authenticate and get API key (replace with your TabPFN token)
curl -X POST \
  -H "Content-Type: application/json" \
  "$SERVICE_URL/api/v1/auth/setup" \
  -d '{"tabpfn_token": "YOUR_TABPFN_TOKEN"}'

# Save the API key
API_KEY="the_api_key_from_above_response"

# Train a model with CSV upload
curl -X POST \
  -H "Authorization: Bearer $API_KEY" \
  -F "file=@path/to/your/data.csv" \
  "$SERVICE_URL/api/v1/models/fit/upload?target_column=label"

# Make predictions with CSV upload (replace MODEL_ID with value from training response)
curl -X POST \
  -H "Authorization: Bearer $API_KEY" \
  -F "file=@path/to/your/prediction_data.csv" \
  "$SERVICE_URL/api/v1/models/MODEL_ID/predict/upload?task=classification"
```

### Automated Testing with Python

Use the test script in `tests/manual_tests/test_deployed_api.py`:

```bash
# Install required packages
pip install requests pandas

# Run the test script
python tests/manual_tests/test_deployed_api.py \
  --url $SERVICE_URL \
  --token YOUR_TABPFN_TOKEN \
  --output test_results.json
```

The script will:
1. Test the health endpoint
2. Authenticate with your token
3. Create and upload sample CSV files
4. Train a model
5. Make predictions
6. Save all results to the specified output file

## Common Issues & Troubleshooting

### Permission Issues

**Symptom**: Error messages containing "permission denied" or "Permission error"

**Solution**: 
- Ensure the service account has the necessary permissions
- Check that the container user has access to required directories
- In Docker container: verify file permissions match the user running the application

### Secret Access Issues

**Symptom**: Errors about missing secrets or cannot access secrets

**Solution**:
- Verify secret names match exactly what's in Secret Manager
- Check that the service account has Secret Accessor role
- Ensure secrets are created in the correct project

### Build Issues on Apple Silicon

**Symptom**: Slow builds or architecture compatibility errors

**Solution**:
- Always use `--platform linux/amd64` when building on Apple Silicon
- Consider using Cloud Build for faster remote builds
- For local testing, use Docker's Rosetta mode

## Maintenance

### Updating a Deployed Service

```bash
# Rebuild image with version tag
docker buildx build --platform linux/amd64 \
  -t $REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/$IMAGE_NAME:v1.x.x .

# Push the new version
docker push $REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/$IMAGE_NAME:v1.x.x

# Update the deployment
gcloud run deploy SERVICE_NAME \
  --image $REGION-docker.pkg.dev/$PROJECT_ID/$REPOSITORY/$IMAGE_NAME:v1.x.x \
  --platform managed \
  --region $REGION
```

### Monitoring

Monitor your deployed service via Google Cloud Console:
- Cloud Run > Select your service > Metrics
- Cloud Logging > Build a query focusing on your service

Set up alerts for:
- High error rates
- Increased latency
- Memory utilization spikes 