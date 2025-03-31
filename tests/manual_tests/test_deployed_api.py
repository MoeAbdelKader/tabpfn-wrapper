#!/usr/bin/env python3
"""
Test script for the deployed TabPFN Wrapper API.
Tests health check, authentication, and CSV upload endpoints.
"""

import requests
import argparse
import json
import os
import time
import pandas as pd
import io

def create_test_csv_files():
    """Create test CSV files for training and prediction."""
    # Create a training CSV with a target column
    train_data = {
        "feature1": [1.0, 2.0, 3.0, 4.0, 5.0],
        "feature2": [0.1, 0.2, 0.3, 0.4, 0.5],
        "label": [0, 1, 0, 1, 0]
    }
    train_df = pd.DataFrame(train_data)
    train_file = "train_data.csv"
    train_df.to_csv(train_file, index=False)
    print(f"Created training file: {train_file}")
    
    # Create a prediction CSV without the target column
    predict_data = {
        "feature1": [1.5, 2.5, 3.5],
        "feature2": [0.15, 0.25, 0.35]
    }
    predict_df = pd.DataFrame(predict_data)
    predict_file = "predict_data.csv"
    predict_df.to_csv(predict_file, index=False)
    print(f"Created prediction file: {predict_file}")
    
    return train_file, predict_file

def test_api(base_url, tabpfn_token, train_file, predict_file):
    """Test all API endpoints."""
    results = {}
    
    # Test 1: Health check
    print("\n1. Testing health endpoint...")
    health_url = f"{base_url}/health"
    try:
        response = requests.get(health_url)
        response.raise_for_status()
        results["health"] = {
            "status": "SUCCESS",
            "status_code": response.status_code,
            "message": response.json()
        }
        print(f"  ✅ Health check successful: {response.json()}")
    except Exception as e:
        results["health"] = {
            "status": "FAILED",
            "error": str(e)
        }
        print(f"  ❌ Health check failed: {str(e)}")
        return results  # Stop if health check fails
    
    # Test 2: Authentication
    print("\n2. Testing authentication...")
    auth_url = f"{base_url}/api/v1/auth/setup"
    auth_data = {"tabpfn_token": tabpfn_token}
    
    try:
        response = requests.post(auth_url, json=auth_data)
        response.raise_for_status()
        api_key = response.json().get("api_key")
        results["auth"] = {
            "status": "SUCCESS",
            "status_code": response.status_code,
            "api_key": api_key
        }
        print(f"  ✅ Authentication successful. API key received.")
    except Exception as e:
        results["auth"] = {
            "status": "FAILED",
            "error": str(e)
        }
        print(f"  ❌ Authentication failed: {str(e)}")
        return results  # Stop if authentication fails
    
    # Headers for authenticated requests
    auth_headers = {"Authorization": f"Bearer {api_key}"}
    
    # Test 3: CSV upload for training
    print("\n3. Testing model training with CSV upload...")
    train_url = f"{base_url}/api/v1/models/fit/upload?target_column=label"
    
    try:
        with open(train_file, "rb") as f:
            files = {"file": (train_file, f, "text/csv")}
            response = requests.post(train_url, headers=auth_headers, files=files)
            response.raise_for_status()
            model_id = response.json().get("internal_model_id")
            results["train"] = {
                "status": "SUCCESS",
                "status_code": response.status_code,
                "model_id": model_id
            }
            print(f"  ✅ Model training successful. Model ID: {model_id}")
    except Exception as e:
        results["train"] = {
            "status": "FAILED",
            "error": str(e),
            "response": response.text if 'response' in locals() else None
        }
        print(f"  ❌ Model training failed: {str(e)}")
        if 'response' in locals():
            print(f"  Response: {response.text}")
        return results  # Stop if training fails
    
    # Add a delay to allow the server to process the model
    print("  Waiting for 3 seconds to allow the server to process the model...")
    time.sleep(3)
    
    # Test 4: CSV upload for prediction
    print("\n4. Testing prediction with CSV upload...")
    predict_url = f"{base_url}/api/v1/models/{model_id}/predict/upload?task=classification"
    
    try:
        with open(predict_file, "rb") as f:
            files = {"file": (predict_file, f, "text/csv")}
            response = requests.post(predict_url, headers=auth_headers, files=files)
            response.raise_for_status()
            predictions = response.json().get("predictions")
            results["predict"] = {
                "status": "SUCCESS",
                "status_code": response.status_code,
                "predictions": predictions
            }
            print(f"  ✅ Prediction successful. Predictions: {predictions}")
    except Exception as e:
        results["predict"] = {
            "status": "FAILED",
            "error": str(e),
            "response": response.text if 'response' in locals() else None
        }
        print(f"  ❌ Prediction failed: {str(e)}")
        if 'response' in locals():
            print(f"  Response: {response.text}")
    
    return results

def main():
    """Main function to parse arguments and run tests."""
    parser = argparse.ArgumentParser(description="Test the deployed TabPFN Wrapper API")
    parser.add_argument("--url", required=True, help="Base URL of the deployed API (e.g., https://tabpfn-wrapper-api-xyz.run.app)")
    parser.add_argument("--token", required=True, help="Your TabPFN API token")
    parser.add_argument("--train-file", help="Path to training CSV file (will be created if not provided)")
    parser.add_argument("--predict-file", help="Path to prediction CSV file (will be created if not provided)")
    parser.add_argument("--output", help="Path to save test results as JSON")
    
    args = parser.parse_args()
    
    # Create test files if not provided
    train_file = args.train_file
    predict_file = args.predict_file
    if not train_file or not predict_file:
        train_file, predict_file = create_test_csv_files()
    
    # Run tests
    print(f"\nTesting API at: {args.url}")
    results = test_api(args.url, args.token, train_file, predict_file)
    
    # Save results if output path is provided
    if args.output:
        with open(args.output, "w") as f:
            json.dump(results, f, indent=2)
        print(f"\nTest results saved to: {args.output}")
    
    # Print overall result
    success = all(result.get("status") == "SUCCESS" for result in results.values())
    print("\n" + "=" * 50)
    if success:
        print("🎉 All tests passed successfully!")
    else:
        print("❌ Some tests failed. Check the output for details.")
    print("=" * 50)
    
    return 0 if success else 1

if __name__ == "__main__":
    exit(main()) 