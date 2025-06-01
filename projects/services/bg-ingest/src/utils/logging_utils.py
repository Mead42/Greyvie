"""
Logging utilities for redacting sensitive data from logs and error messages.

Example:
    from src.utils.logging_utils import redact_sensitive_data
    safe = redact_sensitive_data({'password': 'abc', 'user': 'bob'})
    # safe == {'password': '***REDACTED***', 'user': 'bob'}
"""

import logging
import json
from datetime import datetime

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

class JSONFormatter(logging.Formatter):
    """
    Formats log records as JSON with standard fields.
    """
    def format(self, record):
        log_record = {
            "timestamp": datetime.utcnow().isoformat() + 'Z',
            "level": record.levelname,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno
        }
        if record.exc_info:
            log_record["exception"] = self.formatException(record.exc_info)
        # Add extra fields if present
        if hasattr(record, "extra") and isinstance(record.extra, dict):
            log_record.update(record.extra)
        return json.dumps(log_record)

def setup_json_logging(level=logging.INFO, output='stdout', file_path=None):
    """
    Set up structured JSON logging for the app.
    Args:
        level: Logging level (default: INFO)
        output: 'stdout' or 'file'
        file_path: Path to log file if output is 'file'
    """
    logger = logging.getLogger()
    logger.setLevel(level)
    # Remove existing handlers
    for h in list(logger.handlers):
        logger.removeHandler(h)
    if output == 'file' and file_path:
        handler = logging.FileHandler(file_path)
    else:
        handler = logging.StreamHandler()
    handler.setFormatter(JSONFormatter())
    logger.addHandler(handler)
    return logger

# Usage:
# from src.utils.logging_utils import setup_json_logging
# setup_json_logging(level=logging.INFO) 