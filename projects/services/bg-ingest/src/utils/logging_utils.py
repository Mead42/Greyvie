"""
Logging utilities for redacting sensitive data from logs and error messages.

Example:
    from src.utils.logging_utils import redact_sensitive_data
    safe = redact_sensitive_data({'password': 'abc', 'user': 'bob'})
    # safe == {'password': '***REDACTED***', 'user': 'bob'}
"""

SENSITIVE_KEYS = {'password', 'api_key', 'token', 'secret', 'access_token', 'refresh_token', 'key'}

REDACTED = '***REDACTED***'

def redact_sensitive_data(obj):
    """
    Recursively redacts sensitive fields in dicts/lists.
    Keys matched (case-insensitive): password, api_key, token, secret, access_token, refresh_token, key
    """
    if isinstance(obj, dict):
        return {
            k: (REDACTED if k.lower() in SENSITIVE_KEYS else redact_sensitive_data(v))
            for k, v in obj.items()
        }
    elif isinstance(obj, list):
        return [redact_sensitive_data(i) for i in obj]
    else:
        return obj 