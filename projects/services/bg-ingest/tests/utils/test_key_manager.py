import os
import pytest
import json
from src.utils.key_manager import KeyManager, KEYS_SECRET_NAME, CURRENT_KEY_VERSION_ENV
from datetime import datetime, timedelta

def setup_env_keys(keys_dict, current_version=None):
    os.environ[KEYS_SECRET_NAME] = json.dumps(keys_dict)
    if current_version:
        os.environ[CURRENT_KEY_VERSION_ENV] = current_version
    else:
        os.environ.pop(CURRENT_KEY_VERSION_ENV, None)

def teardown_env_keys():
    os.environ.pop(KEYS_SECRET_NAME, None)
    os.environ.pop(CURRENT_KEY_VERSION_ENV, None)

def test_rotate_key_and_get_current(monkeypatch):
    teardown_env_keys()
    km = KeyManager()
    key1, v1 = km.rotate_key()
    key2, v2 = km.rotate_key()
    assert v2 != v1
    assert key2 != key1
    key, version = km.get_current_key()
    assert version == v2
    assert key == key2
    teardown_env_keys()

def test_get_key_and_list_keys(monkeypatch):
    teardown_env_keys()
    keys = {"v1": "key1", "v2": "key2"}
    setup_env_keys(keys, current_version="v2")
    km = KeyManager()
    assert km.get_key("v1") == "key1"
    assert km.get_key("v2") == "key2"
    all_keys = km.list_keys()
    assert set(all_keys.keys()) == set(keys.keys())
    for meta in all_keys.values():
        assert "created_at" in meta
        assert "key" not in meta  # Should not expose key material
    teardown_env_keys()

def test_missing_key_version(monkeypatch):
    teardown_env_keys()
    keys = {"v1": "key1"}
    setup_env_keys(keys, current_version="v1")
    km = KeyManager()
    with pytest.raises(RuntimeError):
        km.get_key("v2")
    teardown_env_keys()

def test_get_current_key_uses_latest(monkeypatch):
    teardown_env_keys()
    keys = {"v1": "key1", "v2": "key2", "v3": "key3"}
    setup_env_keys(keys)  # No current version set
    km = KeyManager()
    key, version = km.get_current_key()
    assert version == "v3"
    assert key == "key3"
    teardown_env_keys()

def test_rotate_key_adds_created_at(monkeypatch):
    teardown_env_keys()
    km = KeyManager()
    key, v1 = km.rotate_key()
    keys = km.list_keys()
    assert v1 in keys
    assert "created_at" in keys[v1]
    teardown_env_keys()

def test_migrate_old_format(monkeypatch):
    teardown_env_keys()
    # Old format: string values
    old_keys = {"v1": "key1", "v2": "key2"}
    setup_env_keys(old_keys, current_version="v2")
    km = KeyManager()
    # Should migrate to new format
    keys = km.list_keys()
    for meta in keys.values():
        assert "created_at" in meta
    teardown_env_keys()

def test_list_keys_metadata(monkeypatch):
    teardown_env_keys()
    km = KeyManager()
    key, v1 = km.rotate_key()
    key, v2 = km.rotate_key()
    keys = km.list_keys()
    assert set(keys.keys()) == {v1, v2}
    for meta in keys.values():
        assert "created_at" in meta
    teardown_env_keys()

def test_get_key_and_current_key_with_migration(monkeypatch):
    teardown_env_keys()
    old_keys = {"v1": "key1"}
    setup_env_keys(old_keys, current_version="v1")
    km = KeyManager()
    key, version = km.get_current_key()
    assert version == "v1"
    assert isinstance(key, str)
    assert km.get_key("v1") == key
    teardown_env_keys()

def test_error_no_current_key(monkeypatch):
    teardown_env_keys()
    km = KeyManager()
    with pytest.raises(RuntimeError):
        km.get_current_key()
    teardown_env_keys() 