import pytest
from unittest import mock
from datetime import datetime, timedelta
import sys

# Patch KeyManager and sys modules
@pytest.fixture
def fake_km(monkeypatch):
    class FakeKM:
        def __init__(self, created_at):
            self._created_at = created_at
            self._rotated = False
        def list_keys(self):
            return {"v1": {"created_at": self._created_at}}
        def get_current_key(self):
            return ("dummy", "v1")
        def rotate_key(self):
            self._rotated = True
            return ("dummy2", "v2")
    return FakeKM

def run_script_with_km(monkeypatch, created_at, argv):
    monkeypatch.setattr(sys, "argv", argv)
    import importlib
    rotate_keys = importlib.import_module("scripts.rotate_keys")
    monkeypatch.setattr(rotate_keys, "KeyManager", lambda: rotate_keys.KeyManager(created_at))
    return rotate_keys

def test_rotate_if_old(monkeypatch, capsys):
    old_date = (datetime.utcnow() - timedelta(days=91)).isoformat() + 'Z'
    class KM:
        def list_keys(self):
            return {"v1": {"created_at": old_date}}
        def get_current_key(self):
            return ("dummy", "v1")
        def rotate_key(self):
            return ("dummy2", "v2")
    monkeypatch.setattr("src.utils.key_manager.KeyManager", lambda: KM())
    import scripts.rotate_keys as rk
    rk.main()
    out = capsys.readouterr().out
    assert "Rotating" in out and "new key version" in out

def test_warning_if_near_expiry(monkeypatch, capsys):
    warn_date = (datetime.utcnow() - timedelta(days=85)).isoformat() + 'Z'
    class KM:
        def list_keys(self):
            return {"v1": {"created_at": warn_date}}
        def get_current_key(self):
            return ("dummy", "v1")
        def rotate_key(self):
            raise AssertionError("Should not rotate")
    monkeypatch.setattr("src.utils.key_manager.KeyManager", lambda: KM())
    import scripts.rotate_keys as rk
    rk.main()
    out = capsys.readouterr().out
    assert "WARNING" in out

def test_ok_if_fresh(monkeypatch, capsys):
    fresh_date = (datetime.utcnow() - timedelta(days=10)).isoformat() + 'Z'
    class KM:
        def list_keys(self):
            return {"v1": {"created_at": fresh_date}}
        def get_current_key(self):
            return ("dummy", "v1")
        def rotate_key(self):
            raise AssertionError("Should not rotate")
    monkeypatch.setattr("src.utils.key_manager.KeyManager", lambda: KM())
    import scripts.rotate_keys as rk
    rk.main()
    out = capsys.readouterr().out
    assert "safe age window" in out 