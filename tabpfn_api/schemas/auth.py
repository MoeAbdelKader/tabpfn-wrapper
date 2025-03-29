from pydantic import BaseModel, Field

# --- Request Schemas ---

class UserSetupRequest(BaseModel):
    """Schema for the request body of the /auth/setup endpoint."""
    tabpfn_token: str = Field(..., description="The user's valid TabPFN API token.")

    class Config:
        json_schema_extra = {
            "example": {
                "tabpfn_token": "YOUR_VALID_TABPFN_API_TOKEN"
            }
        }


# --- Response Schemas ---

class UserSetupResponse(BaseModel):
    """Schema for the response body of the /auth/setup endpoint."""
    api_key: str = Field(..., description="The newly generated API key for this service.")

    class Config:
        json_schema_extra = {
            "example": {
                "api_key": "service_api_key_example_abcdef123456"
            }
        } 