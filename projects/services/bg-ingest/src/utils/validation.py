from abc import ABC, abstractmethod
import re
from typing import Any, Dict, List, Optional, Tuple

class ValidationError(Exception):
    """Custom exception for validation errors."""
    def __init__(self, message: str, field: Optional[str] = None):
        self.message = message
        self.field = field
        super().__init__(f"{field + ': ' if field else ''}{message}")

class ValidationRule(ABC):
    """Abstract base class for validation rules."""
    @abstractmethod
    def validate(self, data: Dict[str, Any], context: 'ValidationContext') -> None:
        pass

class RequiredFieldRule(ValidationRule):
    def __init__(self, field: str, message: Optional[str] = None):
        self.field = field
        self.message = message or f"Field '{field}' is required."
    def validate(self, data: Dict[str, Any], context: 'ValidationContext') -> None:
        if self.field not in data or data[self.field] is None:
            context.add_error(self.field, self.message)

class TypeRule(ValidationRule):
    def __init__(self, field: str, expected_type: type | tuple, message: Optional[str] = None):
        self.field = field
        self.expected_type = expected_type
        if isinstance(expected_type, tuple):
            type_names = ', '.join([t.__name__ for t in expected_type])
        else:
            type_names = expected_type.__name__
        self.message = message or f"Field '{field}' must be of type {type_names}."
    def validate(self, data: Dict[str, Any], context: 'ValidationContext') -> None:
        if self.field in data and not isinstance(data[self.field], self.expected_type):
            context.add_error(self.field, self.message)

class RangeRule(ValidationRule):
    def __init__(self, field: str, min_value: float, max_value: float, message: Optional[str] = None):
        self.field = field
        self.min_value = min_value
        self.max_value = max_value
        self.message = message or f"Field '{field}' must be between {min_value} and {max_value}."
    def validate(self, data: Dict[str, Any], context: 'ValidationContext') -> None:
        value = data.get(self.field)
        if value is not None:
            try:
                val = float(value)
                if not (self.min_value <= val <= self.max_value):
                    context.add_error(self.field, self.message)
            except (TypeError, ValueError):
                context.add_error(self.field, f"Field '{self.field}' must be a number.")

class PatternRule(ValidationRule):
    def __init__(self, field: str, pattern: str, message: Optional[str] = None):
        self.field = field
        self.pattern = pattern
        self.message = message or f"Field '{field}' does not match required pattern."
    def validate(self, data: Dict[str, Any], context: 'ValidationContext') -> None:
        value = data.get(self.field)
        if value is not None and not re.match(self.pattern, str(value)):
            context.add_error(self.field, self.message)

class ValidationContext:
    """Stores validation errors and state."""
    def __init__(self):
        self.errors: List[Tuple[str, str]] = []
    def add_error(self, field: str, message: str):
        self.errors.append((field, message))
    def has_errors(self) -> bool:
        return len(self.errors) > 0
    def get_errors(self) -> List[Tuple[str, str]]:
        return self.errors

class ValidationEngine:
    """Runs multiple validation rules against data."""
    def __init__(self, rules: List[ValidationRule]):
        self.rules = rules
    def validate(self, data: Dict[str, Any]) -> ValidationContext:
        context = ValidationContext()
        for rule in self.rules:
            rule.validate(data, context)
        return context 