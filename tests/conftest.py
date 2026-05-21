import pytest


@pytest.fixture
def no_audit():
    return lambda tool, params: None
