import pytest
from src.utils.error_handling import ErrorCollector, ErrorSeverity, ValidationError, NormalizationError, SystemError

def test_error_collector_add_and_get():
    collector = ErrorCollector()
    collector.add_error('ValidationError', 'foo', 'Missing field', ErrorSeverity.HIGH)
    collector.add_error('NormalizationError', None, 'Bad format', ErrorSeverity.LOW)
    errors = collector.get_errors()
    assert len(errors) == 2
    assert errors[0]['type'] == 'ValidationError'
    assert errors[0]['field'] == 'foo'
    assert errors[0]['severity'] == 'high'
    assert errors[1]['type'] == 'NormalizationError'
    assert errors[1]['field'] is None
    assert errors[1]['severity'] == 'low'

def test_error_collector_reporting():
    collector = ErrorCollector()
    collector.add_error('ValidationError', 'bar', 'Invalid value', ErrorSeverity.CRITICAL)
    json_report = collector.to_json()
    assert 'Invalid value' in json_report
    human_report = collector.to_human_readable()
    assert '[CRITICAL]' in human_report
    assert 'bar' in human_report

def test_error_classes():
    v = ValidationError('bad', 'f', ErrorSeverity.MEDIUM)
    n = NormalizationError('bad', None, ErrorSeverity.LOW)
    s = SystemError('fail', 'sys', ErrorSeverity.CRITICAL)
    assert isinstance(v, Exception)
    assert v.severity == ErrorSeverity.MEDIUM
    assert n.field is None
    assert s.severity == ErrorSeverity.CRITICAL 