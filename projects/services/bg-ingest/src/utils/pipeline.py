import logging
from typing import Any, Dict, Optional, Tuple
from src.utils.validation import ValidationEngine, ValidationContext, ValidationRule
from src.utils.normalization import (
    normalize_string, normalize_number, normalize_timestamp,
    normalize_trend_direction, normalize_device_info
)

logger = logging.getLogger(__name__)

class DataTransformationPipeline:
    """
    Pipeline to validate and normalize a glucose reading dict.
    """
    def __init__(self, validation_engine: ValidationEngine):
        self.validation_engine = validation_engine

    def process_reading(self, raw: Dict[str, Any]) -> Tuple[Optional[Dict[str, Any]], Optional[Dict[str, Any]]]:
        """
        Validate and normalize a single reading.
        Returns (normalized_reading, errors_dict) where one is None if the other is present.
        """
        # Step 1: Validate
        context = self.validation_engine.validate(raw)
        if context.has_errors():
            logger.warning(f"Validation failed: {context.get_errors()}")
            return None, {field: msg for field, msg in context.get_errors()}

        # Step 2: Normalize
        try:
            normalized = {
                'user_id': normalize_string(raw.get('user_id')),
                'timestamp': normalize_timestamp(raw.get('timestamp') or raw.get('systemTime')),
                'glucose_value': normalize_number(raw.get('glucose_value') or raw.get('value')),
                'trend_direction': normalize_trend_direction(raw.get('trend_direction') or raw.get('trend')),
                'device_info': normalize_device_info(raw.get('device_info', {})),
            }
            return normalized, None
        except Exception as e:
            logger.error(f"Normalization failed: {e}")
            return None, {'normalization_error': str(e)} 