import pytest
from unittest import mock
from src.auth.password_verification import (
    verify_user_password, reset_failed_attempts, is_locked_out,
    generate_reset_token, verify_reset_token, AccountLockedError
)
from src.utils.password_utils import PasswordHasher

USER_ID = "testuser"
PASSWORD = "S3cureP@ssw0rd!"
HASHER = PasswordHasher()
HASH = HASHER.hash_password(PASSWORD)


def get_hash_func(user_id):
    assert user_id == USER_ID
    return HASH

def test_correct_password_resets_failed_attempts():
    reset_failed_attempts(USER_ID)
    assert verify_user_password(USER_ID, PASSWORD, get_hash_func)
    assert not is_locked_out(USER_ID)


def test_incorrect_password_increments_and_locks():
    reset_failed_attempts(USER_ID)
    with mock.patch("time.sleep") as sleep_mock:
        # Attempts 1-4: should return False, no exception
        for i in range(1, 5):
            assert verify_user_password(USER_ID, "wrong", get_hash_func) is False
            assert not is_locked_out(USER_ID)
        # 5th attempt: should raise AccountLockedError and lock the account
        with pytest.raises(AccountLockedError):
            verify_user_password(USER_ID, "wrong", get_hash_func)
        assert is_locked_out(USER_ID)
        # After lockout, should always raise
        with pytest.raises(AccountLockedError):
            verify_user_password(USER_ID, PASSWORD, get_hash_func)


def test_reset_failed_attempts_unlocks():
    reset_failed_attempts(USER_ID)
    # Lock the account
    with mock.patch("time.sleep"):
        for _ in range(5):
            try:
                verify_user_password(USER_ID, "wrong", get_hash_func)
            except AccountLockedError:
                pass
    assert is_locked_out(USER_ID)
    reset_failed_attempts(USER_ID)
    assert not is_locked_out(USER_ID)


def test_progressive_delay():
    reset_failed_attempts(USER_ID)
    with mock.patch("time.sleep") as sleep_mock:
        for i in range(1, 5):
            try:
                verify_user_password(USER_ID, "wrong", get_hash_func)
            except AccountLockedError:
                pass
            # Delay should be 2**(i-1) or max 16
            expected = min(2 ** (i - 1), 16)
            sleep_mock.assert_called_with(expected)


def test_generate_and_verify_reset_token():
    token = generate_reset_token(USER_ID)
    user = verify_reset_token(token)
    assert user == USER_ID
    # Expired token
    from datetime import datetime, timedelta
    expired_time = datetime.utcnow() + timedelta(minutes=31)
    assert verify_reset_token(token, now=expired_time) is None 