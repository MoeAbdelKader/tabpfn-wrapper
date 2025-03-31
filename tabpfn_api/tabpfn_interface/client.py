import logging
import numpy as np
from typing import List, Dict, Any, Union
# Reverting the debug imports - sys and traceback are no longer needed unless debugging further
# import sys 
# import traceback

# --- Debugging Reverted --- 

# Correct import based on documentation and structure
try:
    # ServiceClient is defined in the client.py file
    from tabpfn_client.client import ServiceClient
    from tabpfn_client import set_access_token # Import the function to set token
except ImportError as e:
    # If ServiceClient cannot be imported 
    logging.exception(f"Failed to import from tabpfn_client: {e}")
    raise ImportError(f"Could not import ServiceClient or set_access_token from tabpfn_client. Error: {e}") from e

# Note: Specific exceptions like UsageLimitReached, ConnectionError were not found during import attempts.
# We will rely on catching generic Exception and inspecting the message below.

log = logging.getLogger(__name__)

# --- Custom Exception ---

class TabPFNInterfaceError(Exception):
    """Custom exception for errors originating from the TabPFN interface layer."""
    pass

# --- Fit Function ---

def fit_model(
    tabpfn_token: str,
    features: List[List[Any]],
    target: List[Any],
    config: Dict[str, Any]
) -> str:
    """Calls the TabPFN client to fit a model on the provided data.

    Args:
        tabpfn_token: The user's valid TabPFN API token.
        features: A list of lists representing the feature data (X).
        target: A list representing the target variable (y).
        config: A dictionary of additional configuration options for ServiceClient.fit.

    Returns:
        The train_set_uid returned by the TabPFN client upon successful fitting.

    Raises:
        TabPFNInterfaceError: If data conversion fails or the TabPFN client raises an exception.
    """
    log.info(f"Attempting to fit model via TabPFN client. Feature shape: ({len(features)}, {len(features[0]) if features else 0}), Target length: {len(target)}")

    # 1. Convert input data to NumPy arrays
    try:
        X = np.array(features)
        y = np.array(target)
        log.debug(f"Successfully converted input lists to NumPy arrays. X shape: {X.shape}, y shape: {y.shape}")
    except ValueError as e:
        log.error(f"Failed to convert input lists to NumPy arrays: {e}", exc_info=True)
        raise TabPFNInterfaceError(f"Invalid data format for features or target: {e}") from e
    except Exception as e: # Catch any other unexpected conversion errors
        log.error(f"Unexpected error during NumPy conversion: {e}", exc_info=True)
        raise TabPFNInterfaceError(f"Unexpected error converting data: {e}") from e

    # 2. Set token and call ServiceClient.fit (classmethod)
    try:
        # Set the token globally for the client library before the call
        set_access_token(tabpfn_token)
        log.debug("Access token set via tabpfn_client.set_access_token.")

        # Prepare the config for ServiceClient.fit
        fit_config = {}
        if config is not None:
            # Copy known keys if they exist
            if "tabpfn_systems" in config:
                 fit_config["tabpfn_systems"] = config["tabpfn_systems"]
            # Ensure paper_version is always present, defaulting to False
            fit_config["paper_version"] = config.get("paper_version", False)
        else:
            # Default if no config is provided at all
            fit_config["paper_version"] = False
            # Let the underlying library handle the default for tabpfn_systems if not specified

        log.debug(f"Using config for ServiceClient.fit: {fit_config}")

        # Call fit as a classmethod, passing only data and the prepared config
        train_set_uid = ServiceClient.fit(X, y, config=fit_config)
        log.info(f"TabPFN client fit successful. train_set_uid: {train_set_uid}")
        if not isinstance(train_set_uid, str) or not train_set_uid:
             log.error(f"TabPFN client returned an invalid train_set_uid: {train_set_uid} (Type: {type(train_set_uid)}) ")
             raise TabPFNInterfaceError("TabPFN client returned an invalid or empty train_set_uid.")
        return train_set_uid
    except Exception as e:
        # Catch generic exceptions from the client (set_access_token or fit)
        log.exception(f"TabPFN client interaction failed: {e}")
        # Provide a more generic error message upwards
        raise TabPFNInterfaceError(f"Error during TabPFN operation: {e}") from e

def verify_tabpfn_token(token: str) -> bool:
    """Verifies if a TabPFN token is valid by attempting to fetch API usage.

    Args:
        token: The TabPFN API token to verify.

    Returns:
        True if the token is valid (API usage could be fetched), False otherwise.
    """
    log.debug(f"Verifying TabPFN token (checking usage)...")
    try:
        # Use the access_token parameter as shown in the docs for get_api_usage
        _ = ServiceClient.get_api_usage(access_token=token)

        # If the above call succeeds without error, the token is considered valid.
        log.info(f"TabPFN token verification successful.")
        return True

    # Catch a broad exception since specific ones are unclear/unavailable
    except Exception as e:
        error_message = str(e).lower()
        log.warning(f"An exception occurred during TabPFN token verification: {e}")

        # --- Attempt to categorize the error based on message content --- 
        
        # Check for potential authentication/invalid token errors
        # (Keywords based on common API error patterns)
        if (
            "authentication failed" in error_message or 
            "invalid token" in error_message or 
            "unauthorized" in error_message or 
            "401" in error_message # HTTP 401 Unauthorized
        ):
             log.error(f"TabPFN token verification failed likely due to auth error: {e}")
             return False # Treat as invalid token

        # Check for potential rate limit / usage limit errors
        # (Keywords based on common API error patterns)
        elif (
            "usage limit" in error_message or 
            "rate limit" in error_message or 
            "quota exceeded" in error_message or 
            "too many requests" in error_message or 
            "429" in error_message # HTTP 429 Too Many Requests
        ):
             # IMPORTANT: Even if limit is reached, the token itself is usually VALID.
             log.warning(f"TabPFN token is likely valid, but usage/rate limit reached: {e}")
             return True # Treat as valid token but note the limit

        # Check for potential connection errors
        # (Keywords based on common network error patterns)
        elif (
            "connection error" in error_message or 
            "connection refused" in error_message or
            "timeout" in error_message or
            "network is unreachable" in error_message or
            "dns lookup failed" in error_message or
            "service unavailable" in error_message or # Might overlap with GCPOverloaded
            "503" in error_message # HTTP 503 Service Unavailable
        ):
            log.error(f"TabPFN token verification failed likely due to connection error: {e}")
            return False # Treat as failure (token might be valid, but service unreachable)

        # Check for specific GCPOverloaded exception if library defines it, though import failed earlier
        # elif isinstance(e, GCPOverloaded): 
        #    log.error(f"TabPFN token verification failed due to service overload: {e}")
        #    return False
        
        # If none of the specific patterns match, log as unexpected and treat as failure
        else:
            log.exception(f"An unexpected and unhandled error occurred during TabPFN token verification: {e}")
            return False 

def predict_model(
    tabpfn_token: str,
    train_set_uid: str,
    features: List[List[Any]],
    task: str,
    output_type: str = "mean",
    config: Dict[str, Any] | None = None
) -> Union[List[Any], Dict[str, List[Any]]]:
    """Calls the TabPFN client to get predictions using a previously trained model.

    Args:
        tabpfn_token: The user's valid TabPFN API token.
        train_set_uid: The unique ID of the train set in TabPFN.
        features: A list of lists representing the feature data to predict on.
        task: The type of task ("classification" or "regression").
        output_type: The type of prediction output (e.g., "mean", "median", "mode" for regression).
        config: Optional dictionary of additional configuration options.

    Returns:
        The predictions as a list or a dictionary of lists.

    Raises:
        TabPFNInterfaceError: If data conversion fails or the TabPFN client raises an exception.
    """
    log.info(f"Attempting to get predictions via TabPFN client. Feature shape: ({len(features)}, {len(features[0]) if features else 0})")
    # Ensure config is a dict if None
    tabpfn_config_dict = config or {}
    # Ensure paper_version key exists, defaulting to False if not provided by user
    # This is needed because the client library pops this key.
    if "paper_version" not in tabpfn_config_dict:
        tabpfn_config_dict["paper_version"] = False

    # 1. Convert input data to NumPy array
    try:
        X = np.array(features)
        log.debug(f"Successfully converted input lists to NumPy array. X shape: {X.shape}")
    except ValueError as e:
        log.error(f"Failed to convert input lists to NumPy array: {e}", exc_info=True)
        raise TabPFNInterfaceError(f"Invalid data format for features: {e}") from e
    except Exception as e:
        log.error(f"Unexpected error during NumPy conversion: {e}", exc_info=True)
        raise TabPFNInterfaceError(f"Unexpected error converting data: {e}") from e

    # 2. Set token and call ServiceClient.predict
    try:
        # Set the token globally for the client library
        set_access_token(tabpfn_token)
        log.debug("Access token set via tabpfn_client.set_access_token.")

        # Prepare predict_params dictionary, including output_type for regression
        predict_params_dict = {}
        if task == "regression":
            predict_params_dict["output_type"] = output_type
            # Potentially add other regression-specific params like 'quantiles' here later if needed

        log.debug(f"Using predict_params for ServiceClient.predict: {predict_params_dict}")
        # Ensure the tabpfn_config_dict passed below has paper_version defaulted
        log.debug(f"Using tabpfn_config for ServiceClient.predict: {tabpfn_config_dict}")

        # Call predict with the prepared parameters
        predictions = ServiceClient.predict(
            train_set_uid=train_set_uid,
            x_test=X,
            task=task,
            predict_params=predict_params_dict, # Pass the constructed dict
            tabpfn_config=tabpfn_config_dict # Pass the original config here
        )

        # Convert NumPy array/dict back to Python list/dict
        if isinstance(predictions, dict):
            # Handle case where predictions is a dict (e.g., for quantiles or full output)
            processed_predictions = {k: v.tolist() if isinstance(v, np.ndarray) else v 
                                     for k, v in predictions.items()}
        elif isinstance(predictions, np.ndarray):
            processed_predictions = predictions.tolist()
        else:
            # Should not happen based on docs, but handle just in case
            log.warning(f"Unexpected prediction output type from TabPFN client: {type(predictions)}")
            processed_predictions = predictions

        log.info(f"TabPFN client prediction successful. Output type: {type(processed_predictions)}")
        return processed_predictions

    except Exception as e:
        log.exception(f"TabPFN client prediction failed: {e}")
        # Check if the error message indicates an unexpected keyword argument again
        if "unexpected keyword argument" in str(e):
            log.error("Potential issue with arguments passed to ServiceClient.predict. Check client library signature.")
        raise TabPFNInterfaceError(f"Error during TabPFN prediction: {e}") from e 