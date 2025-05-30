"""
Secrets management abstraction for API keys and sensitive credentials.

- Checks environment variables first (for local/dev)
- Falls back to AWS Secrets Manager in production
- Uses in-memory cache to minimize API calls

Usage:
    from utils.secrets import get_secret
    api_key = get_secret("MY_API_KEY")

Security:
- Never log or print secrets.
- Ensure IAM permissions are restricted in production.
"""
import os
from typing import Optional
from src.utils.config import AwsSecretsManager, get_settings

# In-memory cache for secrets
_secret_cache = {}


def get_secret(key: str) -> Optional[str]:
    """
    Retrieve a secret by key, checking environment variables first, then AWS Secrets Manager if in production.
    Caches secrets in memory after first retrieval.

    Args:
        key (str): The name of the secret
    Returns:
        str or None: The secret value, or None if not found
    Raises:
        RuntimeError: If the secret is not found in any source
    """
    # Check in-memory cache first
    if key in _secret_cache:
        return _secret_cache[key]

    # Check environment variable
    value = os.environ.get(key)
    if value:
        _secret_cache[key] = value
        return value

    # Check AWS Secrets Manager if in production
    settings = get_settings()
    if settings.service_env != "development" and settings.secret_name:
        secrets_manager = AwsSecretsManager(settings.aws_region)
        secrets = secrets_manager.get_secret(settings.secret_name)
        if key in secrets:
            _secret_cache[key] = secrets[key]
            return secrets[key]

    raise RuntimeError(f"Secret '{key}' not found in environment or secrets manager.") 