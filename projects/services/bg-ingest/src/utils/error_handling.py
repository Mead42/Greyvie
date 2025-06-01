from enum import Enum
from typing import Any, Dict, List, Optional
import json

class ErrorSeverity(Enum):
    LOW = 'low'
    MEDIUM = 'medium'
    HIGH = 'high'
    CRITICAL = 'critical'

class PipelineError(Exception):
    """Base class for pipeline errors."""
    def __init__(self, message: str, field: Optional[str] = None, severity: ErrorSeverity = ErrorSeverity.MEDIUM):
        self.message = message
        self.field = field
        self.severity = severity
        super().__init__(f"{field + ': ' if field else ''}{message}")

class ValidationError(PipelineError):
    pass

class NormalizationError(PipelineError):
    pass

class SystemError(PipelineError):
    pass

class ErrorCollector:
    """
    Collects and reports errors during pipeline execution.
    """
    def __init__(self):
        self.errors: List[Dict[str, Any]] = []

    def add_error(self, error_type: str, field: Optional[str], message: str, severity: ErrorSeverity = ErrorSeverity.MEDIUM):
        self.errors.append({
            'type': error_type,
            'field': field,
            'message': message,
            'severity': severity.value
        })

    def has_errors(self) -> bool:
        return len(self.errors) > 0

    def to_json(self) -> str:
        return json.dumps(self.errors, indent=2)

    def to_human_readable(self) -> str:
        return '\n'.join([
            f"[{e['severity'].upper()}] {e['type']} - {e['field'] or ''}: {e['message']}" for e in self.errors
        ])

    def get_errors(self) -> List[Dict[str, Any]]:
        return self.errors

"""
Error Recovery Strategies (to be implemented in pipeline):
- skip: Skip the record and continue processing others
- default: Use a default value for the field and continue
- abort: Stop processing and raise the error
""" 