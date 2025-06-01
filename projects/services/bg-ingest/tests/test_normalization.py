import pytest
from datetime import datetime, timezone
from src.utils.normalization import (
    normalize_string, normalize_number, normalize_timestamp,
    normalize_trend_direction, normalize_device_info
)

def test_normalize_string():
    assert normalize_string('  Hello World  ') == 'hello world'
    assert normalize_string('  Mixed CASE  ', lowercase=False) == 'Mixed CASE'
    assert normalize_string(None) is None
    assert normalize_string('   spaced   out   ') == 'spaced out'

def test_normalize_number():
    assert normalize_number('42.1234', 2) == 42.12
    assert normalize_number(3.14159, 3) == 3.142
    assert normalize_number('not-a-number') is None
    assert normalize_number(None) is None

def test_normalize_timestamp():
    dt = datetime(2024, 6, 1, 12, 0, 0, tzinfo=timezone.utc)
    assert normalize_timestamp(dt).startswith('2024-06-01T12:00:00')
    assert normalize_timestamp('2024-06-01T12:00:00Z').startswith('2024-06-01T12:00:00')
    assert normalize_timestamp('not-a-date') is None
    assert normalize_timestamp(None) is None

def test_normalize_trend_direction():
    assert normalize_trend_direction('Flat') == 'flat'
    assert normalize_trend_direction('RISING') == 'rising'
    assert normalize_trend_direction('steady') == 'flat'
    assert normalize_trend_direction('up') == 'rising'
    assert normalize_trend_direction('down') == 'falling'
    assert normalize_trend_direction('unknown') == 'unknown'
    assert normalize_trend_direction(None) is None

def test_normalize_device_info():
    device = {'id': 'abc', 'serial': '123', 'model': 'X', 'manufacturer': 'Y'}
    norm = normalize_device_info(device)
    assert norm['device_id'] == 'abc'
    assert norm['serial_number'] == '123'
    assert norm['model'] == 'X'
    assert norm['manufacturer'] == 'Y'
    # Defaults
    device = {'device_id': 'd1', 'serial_number': 's1', 'model': 'M'}
    norm = normalize_device_info(device)
    assert norm['device_id'] == 'd1'
    assert norm['serial_number'] == 's1'
    assert norm['manufacturer'] == 'Dexcom' 