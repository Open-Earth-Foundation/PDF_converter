"""Utility function to create a Mistral client."""

import os
from mistralai import Mistral


def create_mistral_client() -> Mistral:
    """Create and return a Mistral client using the MISTRAL_API_KEY environment variable.

    The API key is loaded from the MISTRAL_API_KEY environment variable.
    This function should be called after load_dotenv() has been executed to ensure
    the environment variable is available.

    Returns:
        Mistral: Initialized Mistral client instance.

    Raises:
        RuntimeError: If the MISTRAL_API_KEY environment variable is not set.

    Example:
        >>> from dotenv import load_dotenv
        >>> load_dotenv()
        >>> client = create_mistral_client()
    """
    key = os.environ.get("MISTRAL_API_KEY")
    if not key:
        raise RuntimeError(
            "Missing Mistral API key. Set the MISTRAL_API_KEY environment variable."
        )
    return Mistral(api_key=key)
