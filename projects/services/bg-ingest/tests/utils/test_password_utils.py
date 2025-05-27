import pytest
from src.utils.password_utils import PasswordHasher

def test_password_hash_and_verify():
    hasher = PasswordHasher()
    password = "S3cureP@ssw0rd!"
    hash = hasher.hash_password(password)
    assert hasher.verify_password(hash, password)
    assert not hasher.verify_password(hash, "wrongpassword")


def test_empty_password_raises():
    hasher = PasswordHasher()
    with pytest.raises(ValueError):
        hasher.hash_password("")
    with pytest.raises(ValueError):
        hasher.hash_password(None)


def test_unicode_and_long_passwords():
    hasher = PasswordHasher()
    unicode_pw = "密码🔒Pässwörd"
    hash = hasher.hash_password(unicode_pw)
    assert hasher.verify_password(hash, unicode_pw)
    long_pw = "a" * 1000
    hash2 = hasher.hash_password(long_pw)
    assert hasher.verify_password(hash2, long_pw)


def test_needs_rehash():
    hasher = PasswordHasher(time_cost=2)
    password = "rehashme"
    hash = hasher.hash_password(password)
    # Now create a hasher with higher time_cost
    hasher2 = PasswordHasher(time_cost=4)
    assert hasher2.needs_rehash(hash) 