from pydantic import BaseModel, Field, field_validator, model_validator, ValidationInfo
from typing import List, Dict, Any, Optional, Union
import uuid
from datetime import datetime

# --- Base Schemas (Optional, for common fields) ---

class ModelBase(BaseModel):
    pass

# --- Fit Endpoint Schemas ---

class ModelFitRequest(BaseModel):
    """Schema definition for the request body of the POST /models/fit endpoint."""
    features: List[List[Any]] = Field(
        ...,
        description="Feature data as a list of lists (rows). Must contain uniform data types usable by TabPFN (numeric or string).",
        min_length=1
    )
    target: List[Any] = Field(
        ...,
        description="Target variable as a list. Length must match the number of rows in 'features'.",
        min_length=1
    )
    feature_names: Optional[List[str]] = Field(
        None,
        description="Optional list of feature names. If provided, length must match the number of columns in 'features'.",
        min_length=1
    )
    config: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional dictionary of configuration options passed directly to TabPFN client's fit method (e.g., {'paper_version': True})."
    )

    # Add Config with example
    class Config:
        json_schema_extra = {
            "example": {
                "features": [[1.0, 2.5, "A"], [3.0, 4.0, "B"], [0.5, 1.2, "A"]],
                "target": [0, 1, 0],
                "feature_names": ["numeric_feat1", "numeric_feat2", "categorical_feat"],
                "config": {"paper_version": False}
            }
        }

    @field_validator('features')
    def check_features_non_empty_rows(cls, v):
        if not v: # Already checked by min_length, but good practice
            raise ValueError("Features list cannot be empty.")
        if not all(v): # Check if any inner list (row) is empty
            raise ValueError("Feature rows cannot be empty lists.")
        return v

    @model_validator(mode='after')
    def check_dimensions_match(self) -> 'ModelFitRequest':
        if not self.features or not self.target:
            # Should have been caught by individual field validators, but defensive check
            return self # Or raise error

        # Check if all feature rows have the same number of columns
        first_row_len = len(self.features[0])
        if not all(len(row) == first_row_len for row in self.features):
            raise ValueError("All feature rows must have the same number of columns.")

        # Check if number of feature rows matches number of target values
        if len(self.features) != len(self.target):
            raise ValueError("Number of feature rows must match the number of target values.")

        # Check feature_names length if provided
        if self.feature_names is not None:
            if first_row_len == 0:
                 raise ValueError("Cannot provide feature names when feature rows are empty.")
            if len(self.feature_names) != first_row_len:
                raise ValueError("Number of feature names must match the number of columns in features.")

        return self

class ModelFitResponse(BaseModel):
    """Schema definition for the response body of the POST /models/fit endpoint."""
    internal_model_id: str = Field(..., description="The unique internal UUID assigned to the successfully trained model. Use this ID for prediction requests.")

    # Add Config with example
    class Config:
        json_schema_extra = {
            "example": {
                "internal_model_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479"
            }
        }


# --- Predict Endpoint Schemas ---

class ModelPredictRequest(BaseModel):
    """Schema definition for the request body of the POST /models/{model_id}/predict endpoint."""
    features: List[List[Any]] = Field(
        ...,
        description="Feature data (list of lists/rows) to generate predictions for. Must match the feature structure of the training data.",
        min_length=1
    )
    task: str = Field(
        ...,
        description="Task type: 'classification' or 'regression'. Must match the task the model was trained for.",
        pattern="^(classification|regression)$"
    )
    output_type: str = Field(
        default="mean",
        description="Specifies output format for regression tasks ('mean', 'median', 'mode', 'quantiles', 'full', 'main'). Ignored for classification."
    )
    config: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional dictionary of configuration options passed directly to TabPFN client's predict method."
    )

    # Add Config with example
    class Config:
        json_schema_extra = {
            "example": {
                "features": [[0.8, 2.1, "A"], [-1.0, 3.5, "C"]],
                "task": "classification",
                "config": {}
            }
        }

    @field_validator('features')
    def check_features_non_empty_rows(cls, v):
        if not v:  # Already checked by min_length, but good practice
            raise ValueError("Features list cannot be empty.")
        if not all(v):  # Check if any inner list (row) is empty
            raise ValueError("Feature rows cannot be empty lists.")
        return v

    @field_validator('output_type')
    def check_output_type(cls, v, values: ValidationInfo):
        if 'task' in values.data and values.data['task'] == 'regression':
            valid_types = {'mean', 'median', 'mode', 'quantiles', 'full', 'main'}
            if v not in valid_types:
                raise ValueError(f"Invalid output_type for regression. Must be one of: {valid_types}")
        return v

class ModelPredictResponse(BaseModel):
    """Schema definition for the response body of the POST /models/{model_id}/predict endpoint."""
    predictions: Union[List[Any], Dict[str, List[Any]]] = Field(
        ...,
        description="The model predictions. Format depends on the task and output_type: List for classification or simple regression, Dict for complex regression outputs (e.g., quantiles)."
    )

    # Add Config with example
    class Config:
        json_schema_extra = {
            "example": {
                "predictions": [0, 1] # Example for classification
            }
        }


# --- List Endpoint Schemas (Placeholder for Milestone 5) ---
# Will be added later 

# --- List Available Models Endpoint Schema (Corrected) ---

class AvailableModelsResponse(BaseModel):
    """Schema definition for the response body of the GET /models/available endpoint."""
    # Update field to be a dictionary
    available_models: Dict[str, List[str]] = Field(..., description="A dictionary containing lists of available pre-trained TabPFN model system names, keyed by task type ('classification' and 'regression').")

    class Config:
        json_schema_extra = {
            "example": {
                "available_models": {
                    "classification": ["default", "gn2p4bpt", "llderlii", "od3j1g5m", "vutqq28w", "znskzxi4"],
                    "regression": ["default", "2noar4o2", "5wof9ojf", "09gpqh39", "wyl4o83o"]
                }
            }
        }


# --- List User Models Endpoint Schemas ---

class UserModelMetadataItem(BaseModel):
    """Schema representing metadata for a single user-trained model."""
    internal_model_id: uuid.UUID = Field(..., description="Internal UUID of the trained model.")
    created_at: datetime = Field(..., description="Timestamp when the model training was completed.")
    feature_count: int = Field(..., description="Number of features in the training dataset.")
    sample_count: int = Field(..., description="Number of samples (rows) in the training dataset.")
    feature_names: Optional[List[str]] = Field(None, description="List of feature names used during training, if provided.")
    tabpfn_config: Optional[Dict[str, Any]] = Field(None, description="TabPFN configuration dictionary used during training, if provided.")
    # We are intentionally NOT exposing the TabPFN train_set_uid here

    class Config:
        # Allow ORM mode to automatically map database model fields to schema fields
        from_attributes = True


class UserModelListResponse(BaseModel):
    """Schema for the response body of the GET /models endpoint."""
    models: List[UserModelMetadataItem] = Field(..., description="A list containing metadata for each model trained by the authenticated user.")

    class Config:
        json_schema_extra = {
            "example": {
                "models": [
                    {
                        "internal_model_id": "f47ac10b-58cc-4372-a567-0e02b2c3d479",
                        "created_at": "2023-10-27T10:30:00Z",
                        "feature_count": 3,
                        "sample_count": 150,
                        "feature_names": ["feat1", "feat2", "feat3"],
                        "tabpfn_config": {"paper_version": False}
                    },
                    {
                        "internal_model_id": "a1b2c3d4-e5f6-7890-1234-567890abcdef",
                        "created_at": "2023-10-28T11:00:00Z",
                        "feature_count": 5,
                        "sample_count": 1000,
                        "feature_names": None,
                        "tabpfn_config": None
                    }
                ]
            }
        }

# --- CSV Upload Endpoint Schemas ---

class ModelCSVFitRequest(BaseModel):
    """Schema definition for the query parameters of the POST /models/fit/upload endpoint."""
    target_column: str = Field(
        ..., 
        description="Name of the column in the CSV to use as the target variable."
    )
    config: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional dictionary of configuration options passed directly to TabPFN client's fit method (e.g., {'paper_version': True})."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "target_column": "species",
                "config": {"paper_version": False}
            }
        }

# Reuse ModelFitResponse for CSV upload response

class ModelCSVPredictRequest(BaseModel):
    """Schema definition for the query parameters of the POST /models/{model_id}/predict/upload endpoint."""
    task: str = Field(
        ...,
        description="Task type: 'classification' or 'regression'. Must match the task the model was trained for.",
        pattern="^(classification|regression)$"
    )
    output_type: str = Field(
        default="mean",
        description="Specifies output format for regression tasks ('mean', 'median', 'mode', 'quantiles', 'full', 'main'). Ignored for classification."
    )
    config: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional dictionary of configuration options passed directly to TabPFN client's predict method."
    )

    class Config:
        json_schema_extra = {
            "example": {
                "task": "classification",
                "output_type": "mean",
                "config": {}
            }
        }

    @field_validator('output_type')
    def check_output_type(cls, v, values: ValidationInfo):
        if 'task' in values.data and values.data['task'] == 'regression':
            valid_types = {'mean', 'median', 'mode', 'quantiles', 'full', 'main'}
            if v not in valid_types:
                raise ValueError(f"Invalid output_type for regression. Must be one of: {valid_types}")
        return v

# Reuse ModelPredictResponse for CSV upload response