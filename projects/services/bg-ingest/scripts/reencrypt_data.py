"""
Re-encrypt Data Migration Script

- Migrates encrypted records to use the latest key version
- Simulates data source with a list of dicts
- Dry-run by default (prints what would change)
- Use --apply to perform the migration
- No sensitive data or key material is printed or logged

Usage:
    python scripts/reencrypt_data.py           # Dry-run (default)
    python scripts/reencrypt_data.py --apply   # Actually perform migration

Extend this script to integrate with your real database.
"""
import sys
from src.utils.key_manager import KeyManager

# Dummy encrypt/decrypt for demonstration

def dummy_decrypt(ciphertext, key):
    # Simulate decryption (do not use in production)
    return f"decrypted({ciphertext})"

def dummy_encrypt(plaintext, key):
    # Simulate encryption (do not use in production)
    return f"encrypted({plaintext})"

def main():
    apply = "--apply" in sys.argv
    km = KeyManager()
    current_key, current_version = km.get_current_key()

    # Simulated data source
    records = [
        {"id": 1, "ciphertext": "abc1", "key_version": "v1"},
        {"id": 2, "ciphertext": "abc2", "key_version": current_version},
        {"id": 3, "ciphertext": "abc3", "key_version": "v2"},
    ]

    print(f"Current key version: {current_version}")
    migrated = 0
    for rec in records:
        if rec["key_version"] != current_version:
            old_version = rec["key_version"]
            old_key = km.get_key(old_version)
            plaintext = dummy_decrypt(rec["ciphertext"], old_key)
            new_ciphertext = dummy_encrypt(plaintext, current_key)
            if apply:
                rec["ciphertext"] = new_ciphertext
                rec["key_version"] = current_version
            print(f"Record {rec['id']}: {old_version} -> {current_version} {'[APPLIED]' if apply else '[DRY-RUN]'}")
            migrated += 1
    print(f"Migration complete. {migrated} record(s) would be updated.")
    if not apply:
        print("Run with --apply to perform the migration.")

if __name__ == "__main__":
    main() 