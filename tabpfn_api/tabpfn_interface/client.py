import logging
# Reverting the debug imports - sys and traceback are no longer needed unless debugging further
# import sys 
# import traceback

# --- Debugging Reverted --- 

# Correct import based on documentation and structure
try:
    # ServiceClient is defined in the client.py file
    from tabpfn_client.client import ServiceClient
except ImportError as e:
    # If ServiceClient cannot be imported 
    logging.exception(f"Failed to import ServiceClient from tabpfn_client.client: {e}")
    raise ImportError(f"Could not import ServiceClient class from tabpfn_client.client. Error: {e}") from e

# Note: Specific exceptions like UsageLimitReached, ConnectionError were not found during import attempts.
# We will rely on catching generic Exception and inspecting the message below.

log = logging.getLogger(__name__)


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