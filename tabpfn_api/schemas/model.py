from pydantic import BaseModel, Field, field_validator, model_validator
from typing import List, Dict, Any, Optional
import uuid

# --- Base Schemas (Optional, for common fields) ---

class ModelBase(BaseModel):
    pass

# --- Fit Endpoint Schemas ---

class ModelFitRequest(BaseModel):
    features: List[List[Any]] = Field(
        ...,
        description="Feature data as a list of lists (rows). Example: [[1, 2.5, 'A'], [3, 4.0, 'B']]",
        min_length=1 # Must have at least one row
    )
    target: List[Any] = Field(
        ...,
        description="Target variable as a list. Example: [0, 1]",
        min_length=1 # Must have at least one target value
    )
    feature_names: Optional[List[str]] = Field(
        None,
        description="Optional list of feature names corresponding to the columns in 'features'.",
        min_length=1
    )
    config: Optional[Dict[str, Any]] = Field(
        None,
        description="Optional dictionary of configuration options passed directly to TabPFN's fit method."
    )

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
    internal_model_id: str = Field(..., description="The unique internal ID assigned to the trained model.")


# --- Predict Endpoint Schemas (Placeholder for Milestone 4) ---
# Will be added later

# --- List Endpoint Schemas (Placeholder for Milestone 5) ---
# Will be added later 