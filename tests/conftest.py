import pytest


@pytest.fixture(autouse=True)
def offline_by_default(monkeypatch):
    """No regression test may accidentally spend provider credits."""
    monkeypatch.setenv("SPECGUARD_PROVIDER", "mock")
