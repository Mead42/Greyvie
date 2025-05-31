"""
Automated Key Rotation Script

- Checks the age of the current encryption key
- Rotates the key if older than 90 days
- Can be scheduled (e.g., via cron) or run manually
- No key material is printed or logged

Usage:
    python scripts/rotate_keys.py
"""
import sys
from datetime import datetime, timedelta
from src.utils.key_manager import KeyManager

ROTATION_DAYS = 90
WARNING_DAYS = 80

def main():
    km = KeyManager()
    keys = km.list_keys()
    key, version = km.get_current_key()
    created_at = keys[version]["created_at"]
    created_dt = datetime.fromisoformat(created_at.replace('Z', ''))
    age_days = (datetime.utcnow() - created_dt).days

    print(f"Current key version: {version}")
    print(f"Key age: {age_days} days (created at {created_at})")

    if age_days >= ROTATION_DAYS:
        print(f"[INFO] Key is {age_days} days old. Rotating...")
        new_key, new_version = km.rotate_key()
        print(f"[SUCCESS] Rotated: new key version is {new_version}")
    elif age_days >= WARNING_DAYS:
        print(f"[WARNING] Key is {age_days} days old. Consider rotating soon.")
    else:
        print(f"[OK] Key is within safe age window.")

if __name__ == "__main__":
    main() 