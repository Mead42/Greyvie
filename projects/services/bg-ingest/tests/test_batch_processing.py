import pytest
from src.utils.pipeline import DataTransformationPipeline
from src.utils.validation import RequiredFieldRule, TypeRule, RangeRule, ValidationEngine
from src.utils.batch_processing import BatchProcessor

def make_engine():
    rules = [
        RequiredFieldRule('user_id'),
        RequiredFieldRule('timestamp'),
        RequiredFieldRule('glucose_value'),
        TypeRule('glucose_value', (int, float)),
        RangeRule('glucose_value', 20, 600),
    ]
    return ValidationEngine(rules)

def make_pipeline():
    return DataTransformationPipeline(make_engine())

def test_batch_all_valid():
    pipeline = make_pipeline()
    batch = BatchProcessor(pipeline)
    records = [
        {'user_id': 'u1', 'timestamp': '2024-06-01T12:00:00Z', 'glucose_value': 100},
        {'user_id': 'u2', 'timestamp': '2024-06-01T13:00:00Z', 'glucose_value': 150},
    ]
    processed, errors = batch.process_batch(records)
    assert len(processed) == 2
    assert not errors.has_errors()
    summary = batch.summary()
    assert summary['processed'] == 2
    assert summary['failed'] == 0

def test_batch_some_invalid():
    pipeline = make_pipeline()
    batch = BatchProcessor(pipeline)
    records = [
        {'user_id': 'u1', 'timestamp': '2024-06-01T12:00:00Z', 'glucose_value': 100},
        {'timestamp': '2024-06-01T13:00:00Z', 'glucose_value': 150},  # missing user_id
        {'user_id': 'u3', 'timestamp': '2024-06-01T14:00:00Z', 'glucose_value': 700},  # out of range
    ]
    processed, errors = batch.process_batch(records)
    assert len(processed) == 1
    assert errors.has_errors()
    summary = batch.summary()
    assert summary['processed'] == 1
    assert summary['failed'] == 2
    assert len(summary['errors']) == 2

def test_batch_abort_on_error():
    pipeline = make_pipeline()
    batch = BatchProcessor(pipeline, error_strategy='abort')
    records = [
        {'user_id': 'u1', 'timestamp': '2024-06-01T12:00:00Z', 'glucose_value': 100},
        {'timestamp': '2024-06-01T13:00:00Z', 'glucose_value': 150},  # missing user_id
        {'user_id': 'u3', 'timestamp': '2024-06-01T14:00:00Z', 'glucose_value': 200},
    ]
    processed, errors = batch.process_batch(records)
    # Should stop after first error
    assert len(processed) == 1
    assert errors.has_errors()
    summary = batch.summary()
    assert summary['processed'] == 1
    assert summary['failed'] == 1 