"""
KeyManager: Encryption key versioning and rotation utility.

- Stores keys and versions in AWS Secrets Manager (or env for dev)
- Supports scheduled and emergency rotation
- Provides key versioning for encryption/decryption
- CLI entrypoint for manual rotation

Usage:
    python src/utils/key_manager.py           # Show current key version and all versions
    python src/utils/key_manager.py rotate    # Rotate and set a new key version (emergency/manual)

Security:
- Never log or print key material
- Use AWS Secrets Manager in production
- In production, restrict CLI usage to authorized admins only
"""
import os
import secrets
import json
import time
from typing import Tuple, Dict, Optional
from src.utils.secrets import get_secret
from datetime import datetime

KEYS_SECRET_NAME = os.environ.get("ENCRYPTION_KEYS_SECRET", "ENCRYPTION_KEYS")
CURRENT_KEY_VERSION_ENV = "CURRENT_KEY_VERSION"

class KeyManager:
    def __init__(self, secret_name: Optional[str] = None):
        self.secret_name = secret_name or KEYS_SECRET_NAME
        # In dev, fallback to env vars
        self.is_dev = os.environ.get("SERVICE_ENV", "development") == "development"

    def _now_iso(self):
        return datetime.utcnow().isoformat() + 'Z'

    def _migrate_keys(self, keys):
        # Support old format: {"v1": "key1"}, new: {"v1": {"key": ..., "created_at": ...}}
        migrated = {}
        for version, value in keys.items():
            if isinstance(value, dict) and "key" in value and "created_at" in value:
                migrated[version] = value
            else:
                migrated[version] = {"key": value, "created_at": self._now_iso()}
        return migrated

    def _load_keys(self) -> Dict[str, Dict[str, str]]:
        """Load all keys from secrets manager or env, and migrate to new format if needed."""
        if self.is_dev:
            keys_json = os.environ.get(self.secret_name)
            if keys_json:
                keys = json.loads(keys_json)
            else:
                keys = {}
        else:
            try:
                keys = get_secret(self.secret_name) or {}
            except Exception:
                keys = {}
        # Always migrate to new format (dict with key/created_at)
        return self._migrate_keys(keys)

    def _save_keys(self, keys: Dict[str, Dict[str, str]]):
        """Save keys to env (dev only). In prod, use AWS CLI or admin tool."""
        if self.is_dev:
            os.environ[self.secret_name] = json.dumps(keys)
        else:
            raise NotImplementedError("Saving keys in production must be done via AWS Secrets Manager admin tools.")

    def get_current_key(self) -> Tuple[str, str]:
        """Return (key, version) for the current key."""
        keys = self._load_keys()
        version = os.environ.get(CURRENT_KEY_VERSION_ENV, None)
        if not version and keys:
            version = sorted(keys.keys())[-1]  # Use latest
        if not version or version not in keys:
            raise RuntimeError("No current key version set or key missing.")
        return keys[version]["key"], version

    def get_key(self, version: str) -> str:
        keys = self._load_keys()
        if version not in keys:
            raise RuntimeError(f"Key version {version} not found.")
        return keys[version]["key"]

    def list_keys(self) -> Dict[str, Dict[str, str]]:
        keys = self._load_keys()
        return {v: {"created_at": d["created_at"]} for v, d in keys.items()}

    def rotate_key(self) -> Tuple[str, str]:
        """Generate a new key, store it, and set as current. Returns (key, version)."""
        keys = self._load_keys()
        new_version = f"v{len(keys) + 1}"
        new_key = secrets.token_urlsafe(32)
        keys[new_version] = {"key": new_key, "created_at": self._now_iso()}
        self._save_keys(keys)
        os.environ[CURRENT_KEY_VERSION_ENV] = new_version
        return new_key, new_version

# CLI entrypoint for manual rotation (dev/demo only)
if __name__ == "__main__":
    import sys
    from datetime import datetime
    km = KeyManager()
    if len(sys.argv) > 1 and sys.argv[1] == "rotate":
        key, version = km.rotate_key()
        now = datetime.utcnow().isoformat() + 'Z'
        print(f"[ROTATE] {now}: Rotated key. New version: {version}")
    elif len(sys.argv) == 1:
        key, version = km.get_current_key()
        print(f"Current key version: {version}")
        print(f"All key versions: {list(km.list_keys().keys())}")
    else:
        print("Usage:")
        print("  python src/utils/key_manager.py           # Show current key version and all versions")
        print("  python src/utils/key_manager.py rotate    # Rotate and set a new key version (emergency/manual)")
        print("\n[SECURITY] In production, restrict CLI usage to authorized admins only.") 