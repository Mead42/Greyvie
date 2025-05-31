# KeyManager: Encryption Key Versioning & Rotation

This document explains how to use the `KeyManager` utility from [`src/utils/key_manager.py`](../../src/utils/key_manager.py) to manage encryption key versioning and rotation for secure data storage.

---

## Why Use KeyManager?
- **Security:** Regularly rotate encryption keys to reduce risk if a key is compromised.
- **Compliance:** Many standards require periodic key rotation.
- **Flexibility:** Supports both scheduled and emergency rotation.
- **Versioning:** Allows decryption of old data with the correct key version.

---

## When to Use
- When encrypting sensitive data at rest (e.g., database fields, API tokens).
- When you need to rotate keys without re-encrypting all data immediately.
- When you want to support key versioning for seamless migration.

---

## Automated & Manual Key Rotation

### Automated Rotation
- Use [`scripts/rotate_keys.py`](../scripts/rotate_keys.py) to check key age and rotate if needed.
- Can be scheduled (e.g., via cron) or run manually.
- **Usage:**
  ```sh
  python scripts/rotate_keys.py           # Dry-run: shows key age, rotates if needed
  ```
- Prints warnings if a key is nearing expiration (80+ days) and rotates if older than 90 days.

### Manual/Emergency Rotation
- Use the CLI entrypoint in [`src/utils/key_manager.py`](../../src/utils/key_manager.py) for immediate rotation.
- **Usage:**
  ```sh
  python src/utils/key_manager.py rotate    # Rotate and set a new key version (emergency/manual)
  ```
- All rotation events are logged with timestamps (never logs key material).
- **Security:** In production, restrict CLI usage to authorized admins only.

---

## Data Re-encryption Migration

- Use [`scripts/reencrypt_data.py`](../scripts/reencrypt_data.py) to migrate encrypted records to the latest key version.
- **Dry-run by default:** Prints what would change, does not modify data.
- **Apply changes:**
  ```sh
  python scripts/reencrypt_data.py --apply   # Actually perform migration
  ```
- Designed for extension to real database integration (currently simulates with in-memory records).
- No sensitive data or key material is printed or logged.

---

## Example Workflow
1. **Rotate keys automatically (scheduled) or manually (emergency).**
2. **Run the migration script to re-encrypt old data with the new key.**
3. **Update all new records to use the latest key version.**
4. **Monitor and audit all key rotation and migration events.**

---

## Security Best Practices
- **Never log or print key material.**
- **Use AWS Secrets Manager in production** for key storage and versioning.
- **Restrict IAM permissions** to only allow access to required secrets.
- **Rotate keys regularly** (e.g., every 90 days) and after any suspected compromise.
- **Store the key version** with each encrypted record for future decryption.
- **Re-encrypt old data** with the new key as part of the rotation process.
- **Restrict CLI and migration scripts to trusted operators/admins.**

---

## Integration Tips
- Store the key version alongside each encrypted value in your database.
- When rotating, update the current version and re-encrypt old data as needed.
- Use the `list_keys()` method to audit all available key versions.
- In production, use admin tools or AWS CLI to update secrets; do not use `_save_keys` directly.
- Extend the migration script to connect to your real database and update records in place.

---

## Troubleshooting
- **Missing key version:** Ensure the key version exists in your secret store.
- **No current key:** Set the `CURRENT_KEY_VERSION` environment variable or ensure at least one key exists.
- **Key not found:** Check that the secret is available in AWS Secrets Manager or your environment.

---

## Reference
- Implementation: [`src/utils/key_manager.py`](../../src/utils/key_manager.py)
- Automated rotation: [`scripts/rotate_keys.py`](../scripts/rotate_keys.py)
- Data migration: [`scripts/reencrypt_data.py`](../scripts/reencrypt_data.py)
- Secrets abstraction: [`src/utils/secrets.py`](../../src/utils/secrets.py) 