import pytest


@pytest.fixture
def no_audit():
    return lambda tool, params: None


@pytest.fixture(autouse=True)
def demo_on(monkeypatch):
    """Existing tests exercise the sample data, which is opt-in."""
    monkeypatch.setenv("DEVOPS_MCP_DEMO", "1")
