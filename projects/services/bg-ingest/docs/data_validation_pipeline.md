# Data Validation, Normalization, and Processing Pipeline

This document describes the architecture and usage of the data validation, normalization, transformation pipeline, error handling, and batch processing modules in the `bg-ingest` service.

---

## Overview

The pipeline ensures that incoming blood glucose readings are:
- **Validated** for required fields, types, and value ranges
- **Normalized** to consistent formats (strings, numbers, timestamps, trend directions, device info)
- **Transformed** into a standard structure for storage or further processing
- **Error-handled** with robust reporting and recovery options
- **Batch-processed** efficiently with progress and error tracking

---

## Validation
- Uses a flexible rule-based framework (`ValidationRule`, `ValidationEngine`)
- Supports required fields, type checking, range validation, and pattern matching
- Easily extensible for custom rules

**Example:**
```python
from src.utils.validation import RequiredFieldRule, TypeRule, RangeRule, ValidationEngine
rules = [
    RequiredFieldRule('user_id'),
    TypeRule('glucose_value', (int, float)),
    RangeRule('glucose_value', 20, 600),
]
engine = ValidationEngine(rules)
```

---

## Normalization
- Functions for strings, numbers, timestamps, trend directions, and device info
- Ensures all data is in a consistent, predictable format

**Example:**
```python
from src.utils.normalization import normalize_string, normalize_number, normalize_timestamp
val = normalize_string('  Hello  ')
num = normalize_number('42.123')
timestamp = normalize_timestamp('2024-06-01T12:00:00Z')
```

---

## Data Transformation Pipeline
- Chains validation and normalization for a single reading
- Returns either a normalized reading or a dictionary of errors

**Example:**
```python
from src.utils.pipeline import DataTransformationPipeline
pipeline = DataTransformationPipeline(engine)
normalized, errors = pipeline.process_reading(raw_reading)
if errors:
    print('Validation/Normalization failed:', errors)
else:
    print('Normalized reading:', normalized)
```

---

## Error Handling
- Centralized error classes (`ValidationError`, `NormalizationError`, `SystemError`)
- `ErrorCollector` aggregates errors with type, field, message, and severity
- Supports reporting as JSON or human-readable text
- Severity levels: LOW, MEDIUM, HIGH, CRITICAL

**Example:**
```python
from src.utils.error_handling import ErrorCollector, ErrorSeverity
collector = ErrorCollector()
collector.add_error('ValidationError', 'field', 'Missing value', ErrorSeverity.HIGH)
print(collector.to_json())
```

---

## Batch Processing
- `BatchProcessor` processes multiple records using the pipeline
- Supports error handling strategies: 'skip' (default), 'abort'
- Tracks processed and failed records, and provides a summary

**Example:**
```python
from src.utils.batch_processing import BatchProcessor
batch = BatchProcessor(pipeline, error_strategy='skip')
processed, errors = batch.process_batch(list_of_records)
print(batch.summary())
```

---

## Error Recovery Strategies
- **skip**: Skip invalid records and continue
- **abort**: Stop processing on first error
- (Planned) **default**: Use default values for missing/invalid fields

---

## Testing & Extensibility
- All modules are covered by unit and integration tests
- Add new validation or normalization rules by subclassing and registering
- Batch processing can be extended for parallelism or custom reporting

---

For more details, see the source code in `src/utils/` and the test cases in `tests/`. 