import pytest
from src.utils.validation import (
    RequiredFieldRule, TypeRule, RangeRule, PatternRule,
    ValidationEngine, ValidationContext
)

def test_required_field_rule():
    rule = RequiredFieldRule('foo')
    context = ValidationContext()
    rule.validate({}, context)
    assert context.has_errors()
    assert context.get_errors()[0][0] == 'foo'

    context = ValidationContext()
    rule.validate({'foo': 123}, context)
    assert not context.has_errors()

def test_type_rule():
    rule = TypeRule('bar', int)
    context = ValidationContext()
    rule.validate({'bar': 'not-an-int'}, context)
    assert context.has_errors()
    assert 'must be of type int' in context.get_errors()[0][1]

    context = ValidationContext()
    rule.validate({'bar': 42}, context)
    assert not context.has_errors()

def test_range_rule():
    rule = RangeRule('baz', 10, 20)
    context = ValidationContext()
    rule.validate({'baz': 5}, context)
    assert context.has_errors()
    assert 'between 10 and 20' in context.get_errors()[0][1]

    context = ValidationContext()
    rule.validate({'baz': 15}, context)
    assert not context.has_errors()

    context = ValidationContext()
    rule.validate({'baz': 'not-a-number'}, context)
    assert context.has_errors()
    assert 'must be a number' in context.get_errors()[0][1]

def test_pattern_rule():
    rule = PatternRule('email', r'^\S+@\S+\.\S+$')
    context = ValidationContext()
    rule.validate({'email': 'not-an-email'}, context)
    assert context.has_errors()
    assert 'does not match required pattern' in context.get_errors()[0][1]

    context = ValidationContext()
    rule.validate({'email': 'user@example.com'}, context)
    assert not context.has_errors()

def test_validation_engine_multiple_rules():
    rules = [
        RequiredFieldRule('foo'),
        TypeRule('foo', int),
        RangeRule('foo', 1, 10)
    ]
    engine = ValidationEngine(rules)
    # Missing field
    context = engine.validate({})
    assert context.has_errors()
    # Wrong type
    context = engine.validate({'foo': 'bar'})
    assert context.has_errors()
    # Out of range
    context = engine.validate({'foo': 20})
    assert context.has_errors()
    # Valid
    context = engine.validate({'foo': 5})
    assert not context.has_errors() 