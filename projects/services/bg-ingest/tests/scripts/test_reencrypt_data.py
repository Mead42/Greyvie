import pytest
import sys
from unittest import mock

@pytest.fixture
def fake_km():
    class FakeKM:
        def __init__(self):
            self.calls = []
        def get_current_key(self):
            return ("newkey", "v3")
        def get_key(self, version):
            return f"key-{version}"
    return FakeKM()

def test_dry_run(monkeypatch, capsys, fake_km):
    monkeypatch.setattr("src.utils.key_manager.KeyManager", lambda: fake_km)
    monkeypatch.setattr("scripts.reencrypt_data.dummy_decrypt", lambda c, k: f"plain-{c}-{k}")
    monkeypatch.setattr("scripts.reencrypt_data.dummy_encrypt", lambda p, k: f"enc-{p}-{k}")
    monkeypatch.setattr(sys, "argv", ["reencrypt_data.py"])
    import importlib
    import scripts.reencrypt_data as reenc
    reenc.main()
    out = capsys.readouterr().out
    assert "[DRY-RUN]" in out
    assert "would be updated" in out

def test_apply(monkeypatch, capsys, fake_km):
    monkeypatch.setattr("src.utils.key_manager.KeyManager", lambda: fake_km)
    monkeypatch.setattr("scripts.reencrypt_data.dummy_decrypt", lambda c, k: f"plain-{c}-{k}")
    monkeypatch.setattr("scripts.reencrypt_data.dummy_encrypt", lambda p, k: f"enc-{p}-{k}")
    monkeypatch.setattr(sys, "argv", ["reencrypt_data.py", "--apply"])
    import importlib
    import scripts.reencrypt_data as reenc
    reenc.main()
    out = capsys.readouterr().out
    assert "[APPLIED]" in out
    assert "would be updated" in out 