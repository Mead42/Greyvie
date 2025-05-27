"""
Password Hashing Utility using Argon2 (argon2-cffi)

- Secure password hashing for user credentials
- Configurable parameters for security/performance
- No logging of sensitive data

Usage:
    from utils.password_utils import PasswordHasher
    hasher = PasswordHasher()
    hash = hasher.hash_password('my_password')
    is_valid = hasher.verify_password(hash, 'my_password')
"""

from argon2 import PasswordHasher as Argon2Hasher
from argon2.exceptions import VerifyMismatchError, VerificationError

class PasswordHasher:
    """
    Secure password hasher using Argon2id.
    - time_cost: Number of iterations (default: 3)
    - memory_cost: Memory usage in kibibytes (default: 65536 = 64MB)
    - parallelism: Number of parallel threads (default: 2)
    """
    def __init__(self, time_cost=3, memory_cost=65536, parallelism=2):
        self._hasher = Argon2Hasher(
            time_cost=time_cost,
            memory_cost=memory_cost,
            parallelism=parallelism
        )

    def hash_password(self, password: str) -> str:
        """Hash a password using Argon2id."""
        if not isinstance(password, str) or not password:
            raise ValueError("Password must be a non-empty string.")
        return self._hasher.hash(password)

    def verify_password(self, hashed: str, password: str) -> bool:
        """Verify a password against a stored Argon2 hash. Returns True if valid."""
        try:
            return self._hasher.verify(hashed, password)
        except (VerifyMismatchError, VerificationError):
            return False

    def needs_rehash(self, hashed: str) -> bool:
        """Check if the hash needs to be upgraded to new parameters."""
        return self._hasher.check_needs_rehash(hashed)

# Security note: Never log or print passwords or hashes in production code. 