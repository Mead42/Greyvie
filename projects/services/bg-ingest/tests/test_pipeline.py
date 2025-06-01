import pytest
from src.utils.pipeline import DataTransformationPipeline
from src.utils.validation import RequiredFieldRule, TypeRule, RangeRule, ValidationEngine

def make_engine():
    rules = [
        RequiredFieldRule('user_id'),
        RequiredFieldRule('timestamp'),
        RequiredFieldRule('glucose_value'),
        TypeRule('glucose_value', (int, float)),
        RangeRule('glucose_value', 20, 600),
    ]
    return ValidationEngine(rules)

def test_pipeline_valid_reading():
    engine = make_engine()
    pipeline = DataTransformationPipeline(engine)
    raw = {
        'user_id': 'User1',
        'timestamp': '2024-06-01T12:00:00Z',
        'glucose_value': 120,
        'trend_direction': 'RISING',
        'device_info': {'id': 'dev1', 'serial': 's1', 'model': 'M'}
    }
    normalized, errors = pipeline.process_reading(raw)
    assert errors is None
    assert normalized['user_id'] == 'user1'
    assert normalized['glucose_value'] == 120.0
    assert normalized['trend_direction'] == 'rising'
    assert normalized['device_info']['device_id'] == 'dev1'

def test_pipeline_missing_required():
    engine = make_engine()
    pipeline = DataTransformationPipeline(engine)
    raw = {
        'timestamp': '2024-06-01T12:00:00Z',
        'glucose_value': 120
    }
    normalized, errors = pipeline.process_reading(raw)
    assert normalized is None
    assert 'user_id' in errors

def test_pipeline_type_and_range():
    engine = make_engine()
    pipeline = DataTransformationPipeline(engine)
    # Wrong type
    raw = {
        'user_id': 'u',
        'timestamp': '2024-06-01T12:00:00Z',
        'glucose_value': 'not-a-number'
    }
    normalized, errors = pipeline.process_reading(raw)
    assert normalized is None
    assert 'glucose_value' in errors
    # Out of range
    raw['glucose_value'] = 700
    normalized, errors = pipeline.process_reading(raw)
    assert normalized is None
    assert 'glucose_value' in errors 