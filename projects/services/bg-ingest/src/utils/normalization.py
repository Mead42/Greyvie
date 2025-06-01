import re
from datetime import datetime, timezone
from typing import Any, Dict, Optional

ISO8601_FORMAT = "%Y-%m-%dT%H:%M:%S.%fZ"


def normalize_string(value: Any, lowercase: bool = True, strip: bool = True) -> Optional[str]:
    """Normalize a string: trim, lowercase, remove extra spaces."""
    if value is None:
        return None
    s = str(value)
    if strip:
        s = s.strip()
    if lowercase:
        s = s.lower()
    s = re.sub(r"\s+", " ", s)
    return s

def normalize_number(value: Any, decimals: int = 2) -> Optional[float]:
    """Convert to float and round to given decimals."""
    try:
        return round(float(value), decimals)
    except (TypeError, ValueError):
        return None

def normalize_timestamp(value: Any) -> Optional[str]:
    """Convert various timestamp formats to UTC ISO 8601 string."""
    if value is None:
        return None
    if isinstance(value, datetime):
        dt = value.astimezone(timezone.utc)
    else:
        try:
            # Try parsing common formats
            dt = datetime.fromisoformat(str(value).replace('Z', '+00:00'))
            dt = dt.astimezone(timezone.utc)
        except Exception:
            return None
    return dt.strftime(ISO8601_FORMAT)

def normalize_trend_direction(value: Any) -> Optional[str]:
    """Standardize trend direction values (e.g., 'Flat', 'flat', 'FLAT' -> 'flat')."""
    if value is None:
        return None
    mapping = {
        'flat': 'flat',
        'rising': 'rising',
        'falling': 'falling',
        'rapidly rising': 'rapidly rising',
        'rapidly falling': 'rapidly falling',
        'steady': 'flat',
        'up': 'rising',
        'down': 'falling',
    }
    val = str(value).strip().lower()
    return mapping.get(val, val)

def normalize_device_info(device: Dict[str, Any]) -> Dict[str, Any]:
    """Ensure consistent device info format (keys: id, serial, model, manufacturer)."""
    return {
        'device_id': device.get('device_id') or device.get('id'),
        'serial_number': device.get('serial_number') or device.get('serial'),
        'model': device.get('model'),
        'manufacturer': device.get('manufacturer', 'Dexcom'),
    } 