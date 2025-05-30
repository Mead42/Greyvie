"""
Secure password verification and failed attempt handling.

- Constant-time password verification (Argon2)
- Account lockout after N failed attempts
- Progressive delays (exponential backoff)
- Password reset token generation/verification
- Logging for suspicious activity (never log passwords/hashes)

Usage:
    from src.auth.password_verification import verify_user_password, reset_failed_attempts, is_locked_out
    
    # Example:
    def get_user_hash(user_id):
        ... # fetch hash from DB
    try:
        ok = verify_user_password(user_id, input_password, get_user_hash)
    except AccountLockedError:
        ... # handle lockout

Security:
- Use a persistent store for lockouts in production (e.g., Redis, DB)
- Never log or print passwords or hashes
"""
import time
import logging
import secrets
from datetime import datetime, timedelta
from src.utils.password_utils import PasswordHasher

# Configurable parameters
MAX_FAILED_ATTEMPTS = 5
LOCKOUT_DURATION = timedelta(minutes=15)
MAX_DELAY_SECONDS = 16

# In-memory stores (replace with persistent store in production)
_failed_attempts = {}  # user_id -> (count, last_failed_time)
_lockouts = {}         # user_id -> lockout_until (datetime)

# For password reset tokens
_reset_tokens = {}     # token -> (user_id, expires_at)
RESET_TOKEN_EXPIRY = timedelta(minutes=30)

logger = logging.getLogger(__name__)

class AccountLockedError(Exception):
    pass

def _get_delay(count):
    # Exponential backoff: 1, 2, 4, 8, 16 (max)
    return min(2 ** (count - 1), MAX_DELAY_SECONDS)

def is_locked_out(user_id):
    until = _lockouts.get(user_id)
    if until and until > datetime.utcnow():
        return True
    if until and until <= datetime.utcnow():
        del _lockouts[user_id]
    return False

def reset_failed_attempts(user_id):
    _failed_attempts.pop(user_id, None)
    _lockouts.pop(user_id, None)

def verify_user_password(user_id, password, get_hash_func):
    """
    Verify a user's password with lockout and delay protection.
    Args:
        user_id: Unique user identifier
        password: Password to check
        get_hash_func: Callable that returns the stored hash for the user
    Returns:
        bool: True if password is correct
    Raises:
        AccountLockedError: If the account is locked out
    """
    if is_locked_out(user_id):
        logger.warning(f"Account locked out for user_id={user_id}")
        raise AccountLockedError("Account is locked due to too many failed attempts.")

    hasher = PasswordHasher()
    stored_hash = get_hash_func(user_id)
    ok = hasher.verify_password(stored_hash, password)
    if ok:
        reset_failed_attempts(user_id)
        logger.info(f"Successful login for user_id={user_id}")
        return True
    # Failed attempt
    count, last_time = _failed_attempts.get(user_id, (0, None))
    count += 1
    _failed_attempts[user_id] = (count, datetime.utcnow())
    logger.warning(f"Failed login attempt {count} for user_id={user_id}")
    if count >= MAX_FAILED_ATTEMPTS:
        _lockouts[user_id] = datetime.utcnow() + LOCKOUT_DURATION
        logger.error(f"User {user_id} locked out until {_lockouts[user_id]}")
        # Raise immediately on the Nth failed attempt
        raise AccountLockedError("Account is locked due to too many failed attempts.")
    # Progressive delay
    delay = _get_delay(count)
    time.sleep(delay)
    return False

def generate_reset_token(user_id):
    token = secrets.token_urlsafe(32)
    expires_at = datetime.utcnow() + RESET_TOKEN_EXPIRY
    _reset_tokens[token] = (user_id, expires_at)
    logger.info(f"Generated password reset token for user_id={user_id}")
    return token

def verify_reset_token(token, now=None):
    data = _reset_tokens.get(token)
    if not data:
        return None
    user_id, expires_at = data
    if now is None:
        now = datetime.utcnow()
    if expires_at < now:
        _reset_tokens.pop(token, None)
        return None
    return user_id 